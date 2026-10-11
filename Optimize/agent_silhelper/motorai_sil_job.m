function motorai_sil_job(requestFile)
% Prepare a saved candidate's SIL contract, or run it without Python Engine.
request = jsondecode(fileread(requestFile));
result = struct('status', 'failed', 'diagnostics', struct('error_msg', ''), ...
    'raw_scopes', struct());
try
    modelFile = char(request.model_path);
    root = char(request.gmp_root);
    release = ['R', version('-release')];
    if ~ismember(release, {'R2022b', 'R2023a', 'R2023b', 'R2024a', 'R2024b', 'R2025a', 'R2025b'})
        error('MotorAI:MATLABRelease', 'Use MATLAB R2022b through R2025b.');
    end
    installed = fullfile(root, 'slib', 'install_path', release);
    if ~isfolder(installed)
        error('MotorAI:MissingLibrary', 'Install GMP Simulink libraries for %s first.', release);
    end
    addpath(installed, fullfile(installed, 'src'));
    % Use the canonical MATLAB protocol helpers, even if an older library is installed.
    addpath(fullfile(root, 'slib', 'simulink_lib_src', 'src'), '-begin');
    modelDirectory = fileparts(modelFile);
    cd(modelDirectory);
    addpath(modelDirectory);
    [~, model] = fileparts(modelFile);
    if bdIsLoaded(model)
        loadedFile = get_param(model, 'FileName');
        if ~strcmp(get_param(model, 'SimulationStatus'), 'stopped')
            error('MotorAI:ModelBusy', 'The requested model name is already simulating.');
        end
        if ~strcmpi(loadedFile, modelFile)
            if strcmp(get_param(model, 'Dirty'), 'on')
                error('MotorAI:UnsavedModel', 'Save or close the other loaded model named %s first.', model);
            end
            close_system(model, 0);
        end
    end
    load_system(modelFile);
    cores = find_system(model, 'LookUnderMasks', 'all', 'FollowLinks', 'on', ...
        'BlockType', 'S-Function', 'FunctionName', 'GMP_SIL_Core');
    if numel(cores) ~= 1
        error('MotorAI:SILCoreCount', 'Expected exactly one GMP_SIL_Core, found %d.', numel(cores));
    end
    core = cores{1};
    if ~any(strcmp(get_param(core, 'MaskNames'), 'MaskTransport'))
        % Keep all plant/channel parameters; disconnect only the legacy SIL panel links.
        ancestors = {};
        block = core;
        while ~strcmp(block, model)
            ancestors{end+1} = block; %#ok<AGROW>
            block = get_param(block, 'Parent');
        end
        for index = numel(ancestors):-1:1
            block = ancestors{index};
            if ~strcmp(get_param(block, 'LinkStatus'), 'none')
                set_param(block, 'LinkStatus', 'none');
            end
        end
        save_system(model, modelFile);
        close_system(model, 0);
        upgrade_gmp_sil_core_transport_mask(modelFile);
        load_system(modelFile);
    end
    ensureMex(root, modelDirectory, release);
    network = request.network;
    set_param(core, 'MaskTransport', upper(char(network.transport)), ...
        'MaskHostAddr', ['''', char(network.target_address), ''''], ...
        'MaskMsgTxPort', num2str(network.receive_port), ...
        'MaskMsgRxPort', num2str(network.transmit_port));
    names = cellstr(string(request.scope_vars));
    configureScopeLogging(model, names);
    % Save before computing the path-bound identity. Compilation does not open a SIL session.
    save_system(model, modelFile);
    set_param(model, 'SimulationCommand', 'update');
    contract = jsondecode(fileread(fullfile(modelDirectory, 'network.json')));
    if contract.simulink_to_controller_bytes ~= 264 || contract.controller_to_simulink_bytes ~= 200
        error('MotorAI:SILABI', 'Model packing does not match MotorAI dp_sil buffers (264/200 bytes).');
    end
    expected = char(request.expected_connection_id);
    if ~isempty(expected) && ~strcmp(expected, contract.connection_id)
        error('MotorAI:SILIdentity', 'Model contract changed after controller preparation; prepare and restart it.');
    end
    result.network_config = contract;
    result.status = 'prepared';
    if strcmp(request.action, 'run')
        if request.open_model_ui, open_system(model); end
        for index = 1:numel(names)
            if ~isvarname(names{index}), error('MotorAI:ScopeName', 'Invalid Scope variable.'); end
            evalin('base', ['clear ', names{index}]);
        end
        started = tic;
        output = sim(model);
        result.diagnostics.execution_time_sec = toc(started);
        result.diagnostics.resolved_model = model;
        result.diagnostics.model_sim_status = get_param(model, 'SimulationStatus');
        for index = 1:numel(names)
            name = names{index};
            try
                try
                    value = output.get(name);
                    if isempty(value), value = evalin('base', name); end
                catch
                    value = evalin('base', name);
                end
                result.raw_scopes.(name) = scopePayload(value);
            catch scopeError
                result.raw_scopes.(name) = struct('error', scopeError.message);
            end
        end
        result.status = 'done';
    end
catch failure
    result.diagnostics.error_msg = getReport(failure, 'extended', 'hyperlinks', 'off');
end
file = fopen(request.result_path, 'w', 'n', 'UTF-8');
if file < 0, error('MotorAI:ResultWrite', 'Cannot write MATLAB job result.'); end
cleanup = onCleanup(@() fclose(file));
fprintf(file, '%s', jsonencode(result));
end

function configureScopeLogging(model, names)
% Reuse the model's logging cadence; don't enable nested diagnostic Scopes
% that share a workspace name with a selected top-level measurement Scope.
if isempty(names), return; end
scopes = find_system(model, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'BlockType', 'Scope');
sourceFile = fullfile(fileparts(get_param(model, 'FileName')), 'scope_sources.json');
sources = struct();
if isfile(sourceFile), sources = jsondecode(fileread(sourceFile)); end
selected = cell(size(names));
for index = 1:numel(names)
    if ~isvarname(names{index}), error('MotorAI:ScopeName', 'Invalid Scope variable.'); end
    if isfield(sources, names{index})
        block = [model, '/', char(sources.(names{index}))];
        matches = find(strcmp(scopes, block));
    else
        configs = cellfun(@(block) get_param(block, 'ScopeConfiguration'), scopes, 'UniformOutput', false);
        matches = find(cellfun(@(cfg) strcmp(cfg.DataLoggingVariableName, names{index}), configs));
    end
    if isempty(matches)
        error('MotorAI:MissingScope', 'No Scope logs workspace variable %s.', names{index});
    end
    depth = cellfun(@(block) count(block, '/'), scopes(matches));
    matches = matches(depth == min(depth));
    if numel(matches) ~= 1
        error('MotorAI:AmbiguousScope', 'Multiple measurement Scopes log %s; give them unique names.', names{index});
    end
    selected{index} = get_param(scopes{matches}, 'ScopeConfiguration');
    % Legacy export can drop disabled Scopes' logging names. The model's sidecar
    % identifies the measurement block without touching any signal connections.
    selected{index}.DataLoggingVariableName = names{index};
end
reference = find(cellfun(@(cfg) cfg.DataLogging, selected), 1);
for index = 1:numel(selected)
    cfg = selected{index};
    if ~cfg.DataLogging && ~isempty(reference)
        cfg.DataLoggingSaveFormat = selected{reference}.DataLoggingSaveFormat;
        cfg.DataLoggingDecimateData = selected{reference}.DataLoggingDecimateData;
        cfg.DataLoggingDecimation = selected{reference}.DataLoggingDecimation;
    end
    cfg.DataLogging = true;
    cfg.DataLoggingLimitDataPoints = false;
end
end

function ensureMex(root, modelDirectory, release)
outputDirectory = fullfile(modelDirectory, 'motorai_sil_mex', release);
artifact = fullfile(outputDirectory, ['GMP_SIL_Core.', mexext]);
sourceDirectory = fullfile(root, 'tools', 'gmp_sil', 'sil_helper');
inputs = [dir(fullfile(sourceDirectory, '*.hpp')); dir(fullfile(sourceDirectory, 'GMP_SIL_Core.cpp'))];
built = dir(artifact);
if isempty(built) || any([inputs.datenum] > built.datenum)
    switch computer('arch')
        case 'win64', triplet = 'x64-windows';
        case 'glnxa64', triplet = 'x64-linux';
        otherwise, error('MotorAI:Architecture', 'Unsupported SIL architecture.');
    end
    candidates = {getenv('GMP_SIL_DEPENDENCY_INCLUDE'), ...
        fullfile(getenv('GMP_SIL_DEPENDENCY_ROOT'), 'include'), ...
        fullfile(root, 'bin', 'vcpkg_installed', triplet, triplet, 'include'), ...
        fullfile(modelDirectory, 'vcpkg_installed', triplet, triplet, 'include'), ...
        fullfile(modelDirectory, 'vcpkg_installed', triplet, 'include')};
    include = '';
    for index = 1:numel(candidates)
        if isfile(fullfile(candidates{index}, 'asio.hpp')) && ...
                isfile(fullfile(candidates{index}, 'nlohmann', 'json.hpp'))
            include = candidates{index}; break;
        end
    end
    if isempty(include)
        error('MotorAI:MissingDependencies', 'Restore GMP SIL asio/json dependencies before preparing a model.');
    end
    addpath(sourceDirectory);
    compiler = mex.getCompilerConfigurations('C++', 'Selected');
    if ispc && ~isempty(compiler) && contains(lower(compiler.Manufacturer), 'gnu')
        % The GMP Windows builder supplies MSVC flags. Compile the same canonical
        % source with the flags required by MATLAB's supported MinGW toolchain.
        if ~isfolder(outputDirectory), mkdir(outputDirectory); end
        mex('-R2018a', '-DASIO_STANDALONE', 'CXXFLAGS=$CXXFLAGS -std=c++17', ...
            ['-I', root], ['-I', include], ['-I', fullfile(matlabroot, 'simulink', 'include')], ...
            '-outdir', outputDirectory, '-output', 'GMP_SIL_Core', ...
            fullfile(sourceDirectory, 'GMP_SIL_Core.cpp'), ...
            'LINKLIBS=$LINKLIBS -lws2_32 -lmswsock');
    else
        build_gmp_sil_mex('RepositoryRoot', root, 'DependencyInclude', include, ...
            'OutputDirectory', outputDirectory);
    end
end
clear GMP_SIL_Core;
addpath(outputDirectory, '-begin');
end

function payload = scopePayload(value)
if isa(value, 'timeseries')
    payload = struct('time', value.Time, 'signals', struct('label', 'CH1', 'values', value.Data));
elseif isa(value, 'Simulink.SimulationData.Dataset')
    signals = struct('label', {}, 'values', {});
    times = [];
    for index = 1:numElements(value)
        element = value.get(index);
        label = char(element.Name);
        if isempty(label), label = sprintf('CH%d', index); end
        if isa(element.Values, 'timeseries')
            if isempty(times), times = element.Values.Time; end
            signals(index) = struct('label', label, 'values', element.Values.Data);
        else
            signals(index) = struct('label', label, 'values', element.Values);
        end
    end
    payload = struct('time', times, 'signals', signals);
elseif isstruct(value)
    payload = value;
else
    payload = struct('value', value);
end
end
