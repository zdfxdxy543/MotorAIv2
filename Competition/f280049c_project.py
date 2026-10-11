"""Set up candidate/project/f280049c using the candidate's shared control sources."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = MOTORAI_ROOT / 'Generate/Example/mcs_pmsm_nt'
LOCAL_INCLUDES = ['../../src', 'xplt', 'syscfg']
SYSCONFIG_TOOL = 'com.ti.ccstudio.buildDefinitions.sysConfig'
SYSCONFIG_SCRIPT = '280049C_LaunchPad.syscfg'


def _xml(tree: ET.ElementTree, path: Path) -> None:
    ET.indent(tree, space='\t')
    tree.write(path, encoding='UTF-8', xml_declaration=True)
    if path.name == '.cproject':
        _ensure_cproject_version(path)


def _ensure_cproject_version(path: Path) -> bool:
    """ElementTree drops prolog processing instructions required by CCS/CDT."""
    content = path.read_bytes()
    if b'<?fileVersion' in content:
        return False
    if ET.fromstring(content).tag != 'cproject':
        raise ValueError(f'Not a CDT project description: {path}')
    offset = 3 if content.startswith(b'\xef\xbb\xbf') else 0
    if content[offset:].startswith(b'<?xml'):
        offset = content.index(b'?>', offset) + 2
    path.write_bytes(content[:offset] + b'\n<?fileVersion 4.0.0?>' + content[offset:])
    return True


def _configure_sysconfig(root: Path, *, enable_build: bool = False) -> bool:
    """Restore editor arguments; preserve frozen board sources in older projects."""
    path = root / '.cproject'
    tree = ET.parse(path)
    before = ET.tostring(tree.getroot())
    for configuration in tree.findall('.//configuration'):
        chain = configuration.find('folderInfo/toolChain')
        tool = chain.find(f'tool[@superClass="{SYSCONFIG_TOOL}"]')
        if tool is not None and not enable_build:
            script_option = tool.find(f'option[@superClass="{SYSCONFIG_TOOL}.INPUT_SCRIPT"]')
            if script_option is not None and script_option.get('value') not in (None, '', 'null'):
                continue  # Existing user SysConfig options and build mode are preserved.
        identity = configuration.get('name')
        if tool is None:
            tool = ET.SubElement(chain, 'tool', id=SYSCONFIG_TOOL + '.' + identity,
                                 name='SysConfig', superClass=SYSCONFIG_TOOL)
        for suffix, value in [
            ('INPUT_SCRIPT', '${PROJECT_LOC}/' + SYSCONFIG_SCRIPT),
            ('DEVICE', 'TMS320F280049C'), ('PACKAGE', '100PZ'), ('CONTEXT', 'system'),
            ('PRODUCTS', '${COM_TI_C2000WARE_INSTALL_DIR}/.metadata/sdk.json'),
        ]:
            kind = SYSCONFIG_TOOL + '.' + suffix
            option = tool.find(f'option[@superClass="{kind}"]')
            if option is not None and not enable_build and suffix != 'INPUT_SCRIPT':
                continue
            if option is None:
                option = ET.SubElement(tool, 'option', id=kind + '.' + identity,
                                       superClass=kind,
                                       valueType='stringList' if suffix == 'PRODUCTS' else 'string')
            if suffix == 'PRODUCTS':
                for child in list(option):
                    option.remove(child)
                ET.SubElement(option, 'listOptionValue', builtIn='false', value=value)
            else:
                option.set('value', value)
        if enable_build:
            compiler = next(t for t in chain.findall('tool')
                            if '.compiler' in t.get('superClass', ''))
            includes = compiler.find('option[@valueType="includePath"]')
            value = '${PROJECT_LOC}/${ConfigName}/syscfg'
            if not any(v.get('value') == value for v in includes.findall('listOptionValue')):
                includes.insert(0, ET.Element('listOptionValue', builtIn='false', value=value))
            for entry in configuration.findall('sourceEntries/entry'):
                if entry.get('kind') == 'sourcePath' and entry.get('name') == '':
                    excluded = [v for v in entry.get('excluding', '').split('|')
                                if v and v != SYSCONFIG_SCRIPT]
                    if 'syscfg' not in excluded:
                        excluded.append('syscfg')
                    entry.set('excluding', '|'.join(excluded))
    changed = ET.tostring(tree.getroot()) != before
    if changed:
        _xml(tree, path)
    script = root / SYSCONFIG_SCRIPT
    content = script.read_bytes()
    # This configuration uses only C2000Ware driverlib modules, not the old GMP SDK.
    updated = content.replace(b' --product "gmp_pro@1.00.00.05"', b'')
    if updated != content:
        script.write_bytes(updated)
        changed = True
    return changed


def library_sources(gmp_root: Path, config: dict) -> list[str]:
    """Reuse GMP's dependency resolver and retain paths for CCS linked sources."""
    manager = gmp_root / 'tools/facilities_generator/src_mgr'
    registry = json.loads((manager / 'gmp_framework_dic.json').read_text(encoding='utf-8-sig'))
    resolver = runpy.run_path(str(manager / 'framework_registry.py'))['resolve_selected_modules']
    macros = {**registry.get('macros', {}), 'GMP_PRO_LOCATION': gmp_root.as_posix()}
    files = {}
    for group, module in resolver(registry, config):
        for pattern in registry['modules'][group][module].get('src_patterns', []):
            for key, value in macros.items():
                pattern = pattern.replace('${' + key + '}', value)
            path = Path(pattern)
            matches = Path(path.anchor).glob(str(path.relative_to(path.anchor))) if path.is_absolute() else gmp_root.glob(pattern)
            matched = [p.resolve() for p in matches if p.is_file()]
            if not matched:
                raise FileNotFoundError(f'GMP source pattern has no matches: {pattern}')
            for source in matched:
                if source.suffix.lower() not in ('.c', '.cpp', '.asm'):
                    continue
                relative = source.relative_to(gmp_root).as_posix()
                if source.name in files and files[source.name] != relative:
                    raise ValueError(f'GMP source filename collision: {source.name}')
                files[source.name] = relative
    if not files:
        raise ValueError('The F280049C configuration selected no GMP sources')
    return sorted(files.values())


def configure_ccs(root: Path, gmp_root: Path, gmp_sources: list[str], project_root: Path) -> None:
    project = ET.parse(root / '.project')
    description = project.getroot()
    # A stable unique name permits several MotorAI projects in one CCS workspace.
    identity = hashlib.sha256(str(project_root).encode('utf-8')).hexdigest()[:8]
    description.find('name').text = 'MotorAI_F280049c_' + identity
    for tag in ('linkedResources', 'variableList'):
        element = description.find(tag)
        if element is not None:
            description.remove(element)
    variables = ET.SubElement(description, 'variableList')
    variable = ET.SubElement(variables, 'variable')
    ET.SubElement(variable, 'name').text = 'GMP_ROOT'
    ET.SubElement(variable, 'value').text = gmp_root.as_uri()
    links = ET.SubElement(description, 'linkedResources')
    for name in ('ctl_main.c', 'ctl_main.h', 'user_main.c', 'user_main.h'):
        link = ET.SubElement(links, 'link')
        ET.SubElement(link, 'name').text = 'user/' + name
        ET.SubElement(link, 'type').text = '1'
        ET.SubElement(link, 'locationURI').text = 'PARENT-2-PROJECT_LOC/src/' + name
    for source in gmp_sources:
        link = ET.SubElement(links, 'link')
        ET.SubElement(link, 'name').text = 'gmp_library/' + Path(source).name
        ET.SubElement(link, 'type').text = '1'
        ET.SubElement(link, 'locationURI').text = 'GMP_ROOT/' + source
    _xml(project, root / '.project')


def _configure_build(root: Path, gmp_root: Path) -> None:
    tree = ET.parse(root / '.cproject')
    debug_tags = tree.find('.//option[@superClass="com.ti.ccstudio.buildDefinitions.core.OPT_TAGS"]')
    version = '2.10.00.00'
    registration = gmp_root / '.metadata/.tirex/package.tirex.json'
    if registration.is_file():
        packages = json.loads(registration.read_text(encoding='utf-8-sig'))
        version = next((p['version'] for p in packages if p.get('id') == 'GMP-Core-C28x'), version)
    products = [f'PRODUCTS=GMP-Core-C28x:{version};C2000WARE:5.4.0.00;'] + [
        v.get('value') for v in debug_tags.findall('listOptionValue')
        if v.get('value', '').startswith('PRODUCT_MACRO_IMPORTS=')]
    includes = [
        '${COM_TI_COM_GMP_CORE_C28X_SDK__GMP_PRO_ROOT}',
        '${COM_TI_COM_GMP_CORE_C28X_SDK__GMP_C28X_CSP_ROOT}',
        '${COM_TI_COM_GMP_CORE_C28X_SDK_INCLUDE_PATH}', '${COM_TI_C2000WARE_INCLUDE_PATH}',
        *['${PROJECT_LOC}/' + p for p in LOCAL_INCLUDES], '${CG_TOOL_ROOT}/include',
        '${COM_TI_C2000WARE_INSTALL_DIR}/device_support/f28004x/headers/include',
        '${COM_TI_C2000WARE_INSTALL_DIR}/device_support/f28004x/common/include',
        '${COM_TI_C2000WARE_INSTALL_DIR}/driverlib/f28004x/driverlib',
    ]
    for element in tree.iter():
        if element.tag == 'option':
            kind = element.get('superClass', '')
            values = None
            if kind.endswith('.INCLUDE_PATH'):
                values = includes
            elif kind.endswith('.DEFINE'):
                values = ['${COM_TI_COM_GMP_CORE_C28X_SDK_SYMBOLS}',
                          '${COM_TI_C2000WARE_SYMBOLS}', '_FLASH', 'CPU1', 'F28004x=1']
            elif kind.endswith('.LIBRARY'):
                values = ['libc.a', 'driverlib_eabi.lib']
            elif kind.endswith('.SEARCH_PATH'):
                values = ['${CG_TOOL_ROOT}/lib',
                          '${COM_TI_C2000WARE_INSTALL_DIR}/driverlib/f28004x/driverlib/ccs/Debug']
            elif kind.endswith('.OPT_CODEGEN_VERSION'):
                element.set('value', '22.6.2.LTS')
            elif kind.endswith('.OPT_TAGS'):
                for value in element.findall('listOptionValue'):
                    if value.get('value', '').startswith(('PRODUCTS=', 'PRODUCT_MACRO_IMPORTS=')):
                        element.remove(value)
                for value in products:
                    ET.SubElement(element, 'listOptionValue', builtIn='false', value=value)
            if values is not None:
                for child in list(element):
                    element.remove(child)
                for value in values:
                    ET.SubElement(element, 'listOptionValue', builtIn='false', value=value)
        elif element.tag == 'entry' and element.get('kind') == 'sourcePath':
            element.set('excluding', '280049C_LaunchPad.syscfg|build|Debug|Release')
    # The legacy Release configuration omitted definitions and source exclusions.
    for configuration in tree.findall('.//configuration'):
        compiler = next(t for t in configuration.findall('.//tool')
                        if '.compiler' in t.get('superClass', ''))
        for suffix, value in [('FP_MODE', 'relaxed'), ('OPT_LEVEL', '2')]:
            kind = 'com.ti.ccstudio.buildDefinitions.C2000_22.6.compilerID.' + suffix
            option = compiler.find(f'option[@superClass="{kind}"]')
            if option is None:
                option = ET.SubElement(compiler, 'option', id=kind + '.' + configuration.get('name'),
                                       superClass=kind, valueType='enumerated')
            option.set('value', kind + '.' + value)
        kind = 'com.ti.ccstudio.buildDefinitions.C2000_22.6.compilerID.DEFINE'
        if compiler.find(f'option[@superClass="{kind}"]') is None:
            option = ET.SubElement(compiler, 'option', id=kind + '.' + configuration.get('name'),
                                   superClass=kind, valueType='definedSymbols')
            for value in ['_FLASH', 'CPU1', 'F28004x=1']:
                ET.SubElement(option, 'listOptionValue', builtIn='false', value=value)
        linker = next(t for t in configuration.findall('.//tool')
                      if '.linker' in t.get('superClass', ''))
        kind = 'com.ti.ccstudio.buildDefinitions.C2000_22.6.linkerID.ENTRY_POINT'
        option = linker.find(f'option[@superClass="{kind}"]')
        if option is None:
            option = ET.SubElement(linker, 'option', id=kind + '.' + configuration.get('name'),
                                   superClass=kind, valueType='string')
        option.set('value', 'code_start')
        if configuration.find('sourceEntries') is None:
            entries = ET.SubElement(configuration, 'sourceEntries')
            ET.SubElement(entries, 'entry', excluding='280049C_LaunchPad.syscfg|build|Debug|Release',
                          flags='VALUE_WORKSPACE_PATH|RESOLVED', kind='sourcePath', name='')
    _xml(tree, root / '.cproject')


def copy_f280049c_project(candidate_root: Path, template: Path | None = None, *, gmp_root: Path | None = None) -> Path:
    candidate_root = candidate_root.expanduser().resolve()
    destination = candidate_root / 'project/f280049c'
    if destination.exists():
        if destination.is_symlink() or destination.is_junction() or not (destination / '.cproject').is_file():
            raise FileExistsError(f'Existing f280049c folder is not a CCS project: {destination}')
        _ensure_cproject_version(destination / '.cproject')
        _configure_sysconfig(destination)
        return destination
    template = (template or TEMPLATE).expanduser().resolve()
    original = template / 'project/f280049c'
    if not (original / '.project').is_file():
        raise FileNotFoundError(f'F280049C template is missing: {original}')
    if gmp_root is None:
        configured = os.environ.get('GMP_PRO_LOCATION')
        if not configured:
            raise ValueError('Configure the GMP root before creating the F280049C project')
        gmp_root = Path(configured)
    gmp_root = gmp_root.expanduser().resolve()
    config_path = original / 'gmp_src_mgr/gmp_framework_config.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    external_sources = library_sources(gmp_root, config)
    source = candidate_root / 'src'
    for name in ('ctl_main.c', 'ctl_main.h', 'user_main.c', 'user_main.h'):
        if not (source / name).is_file():
            raise FileNotFoundError(f'Candidate control source is missing: {source / name}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.f280049c_', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'f280049c'
        stage.mkdir()
        for name in ('.project', '.cproject', '.ccsproject', '280049C_LaunchPad.syscfg'):
            shutil.copy2(original / name, stage / name)
        for name in ('xplt', 'device_cmd', 'device_support', 'syscfg', 'target_config'):
            shutil.copytree(original / name, stage / name)
        manager = stage / 'gmp_src_mgr'
        manager.mkdir()
        shutil.copy2(config_path, manager / config_path.name)
        _configure_build(stage, gmp_root)
        _configure_sysconfig(stage, enable_build=True)
        configure_ccs(stage, gmp_root, external_sources, candidate_root)
        for name in ('README.md', 'README_CN.md'):
            shutil.copy2(original / name, stage / name)
        (stage / '.gitignore').write_text('build/\nDebug/\nRelease/\n*.obj\n*.map\n*.out\n', encoding='utf-8')
        # Windows scanners can briefly hold a newly copied project directory open.
        for attempt in range(11):
            try:
                stage.rename(destination)
                break
            except PermissionError:
                if attempt == 10 or destination.exists():
                    raise
                time.sleep(0.1)
    return destination
