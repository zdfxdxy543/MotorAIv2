import json
import re

from PyQt5.QtCore import QThread, pyqtSignal

from widgets.chat import CancellableWorker, call_ui_chat_model


ACTION_CONFIRM_GENERATE = 'confirm_generate'
ACTION_REVISE_PROGRAM = 'revise_program_requirement'
ACTION_SHOW_LOAD_CURVE = 'show_load_curve'
ACTION_SUBMIT_METRICS = 'submit_metrics'
ACTION_ANSWER_QUESTION = 'answer_question'
ACTION_START_TUNING = 'start_tuning'
ACTION_CLARIFY = 'clarify'
ACTION_CONTINUE_NEXT_ROUND = 'continue_next_round'

VALID_ACTIONS = {
    ACTION_CONFIRM_GENERATE,
    ACTION_REVISE_PROGRAM,
    ACTION_SHOW_LOAD_CURVE,
    ACTION_SUBMIT_METRICS,
    ACTION_ANSWER_QUESTION,
    ACTION_START_TUNING,
    ACTION_CLARIFY,
    ACTION_CONTINUE_NEXT_ROUND,
}

ROUTER_SYSTEM_PROMPT = (
    '你是 MotorAI 电机控制程序生成工作台的对话流程路由器。'
    '你的任务不是完成技术设计，而是判断用户当前这句话应该触发哪个工作流动作。'
    'MotorAI 需要收集三类信息：1) 控制程序需求并生成 candidate 程序；'
    '2) 负载曲线；3) 需求指标。'
    '用户在任何阶段都可以补充或修改之前的信息，不能因为当前阶段是指标输入就忽略用户重画负载曲线或修改程序需求的请求。'
    '当用户明确回复“生成程序”或等价确认时，选择 confirm_generate。'
    '当用户补充控制结构、控制策略、候选方案、环路、保护、弱磁、FOC、SVPWM、PID、滑模等程序需求时，选择 revise_program_requirement。'
    '当用户要求设置、修改、重画、查看负载曲线，或提到转速-转矩点、load.csv 时，选择 show_load_curve。'
    '当用户提供超调、调整时间、上升时间、稳态误差、纹波、目标速度、目标电流、电流限制等可评价性能指标时，选择 submit_metrics。'
    '当三类信息都已经准备好，或用户明确要求开始/重新调优时，选择 start_tuning。'
    '当用户明确说"继续仿真""下一轮""开始第二轮""继续迭代"等，表示要基于上一轮结果进行下一轮优化时，选择 continue_next_round。'
    '当用户只是询问、解释、比较或确认概念，并没有提交新信息时，选择 answer_question。'
    '当需要追问才能判断时，选择 clarify。'
    '只输出 JSON，不输出 Markdown。格式：'
    '{"action":"动作名","reply":"可选，面向用户的一句话回答或追问","reason":"简短原因"}'
)


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', '', (text or '').strip().lower())


def _has_negative_generation_intent(normalized: str) -> bool:
    negative_terms = ('不要生成', '别生成', '先不生成', '暂不生成', '不用生成', '不是生成')
    return any(term in normalized for term in negative_terms)


def looks_like_generation_confirmation(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized or _has_negative_generation_intent(normalized):
        return False
    exact_terms = {
        '生成程序',
        '开始生成程序',
        '确认生成程序',
        '确认，生成程序',
        '确认,生成程序',
        '可以生成程序',
        '无误生成程序',
        '没问题生成程序',
        '按这个生成程序',
        '敲定生成程序',
    }
    if normalized in exact_terms:
        return True
    return '生成程序' in normalized and any(term in normalized for term in ('确认', '可以', '开始', '无误', '没问题', '按这个', '敲定'))


def looks_like_load_curve_request(text: str) -> bool:
    normalized = normalize_text(text)
    terms = (
        '负载曲线',
        'load.csv',
        '转速转矩',
        '转速-转矩',
        '转矩点',
        '转速点',
        '重画',
        '重新画',
        '重新设置曲线',
        '修改曲线',
        '改曲线',
        '画曲线',
        '设置曲线',
    )
    return any(term in normalized for term in terms)


def looks_like_question(text: str) -> bool:
    normalized = normalize_text(text)
    if '?' in text or '？' in text:
        return True
    terms = ('为什么', '怎么', '如何', '能否', '可以吗', '是什么', '解释', '区别', '什么意思', '是否')
    return any(term in normalized for term in terms)


def looks_like_metrics_request(text: str) -> bool:
    normalized = normalize_text(text)
    metric_terms = (
        '超调',
        '调整时间',
        '调节时间',
        '上升时间',
        '稳态误差',
        '纹波',
        '响应时间',
        '目标速度',
        '目标转速',
        '目标电流',
        '电流限制',
        '限流',
        '指标',
        '误差小于',
        '不超过',
        '小于',
        '大于',
        'rpm',
        'rad/s',
    )
    return any(term in normalized for term in metric_terms)


def looks_like_program_revision(text: str) -> bool:
    normalized = normalize_text(text)
    program_terms = (
        '补充',
        '修改',
        '改成',
        '换成',
        '增加',
        '加入',
        '支持',
        '取消',
        '不要',
        '候选',
        'candidate',
        '电流环',
        '速度环',
        '位置环',
        '转矩环',
        '弱磁',
        'foc',
        'svpwm',
        'clarke',
        'park',
        'pid',
        'pi',
        '滑模',
        '前馈',
        '抗扰',
        '保护',
        '过流',
        '过压',
    )
    return any(term in normalized for term in program_terms)


def looks_like_next_round_request(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    terms = (
        '继续仿真', '继续迭代', '开始第二轮', '下一轮', '第二轮',
        '继续优化', '接着跑', '再来一轮', '继续调优',
    )
    return any(term in normalized for term in terms)


def looks_like_initial_program_requirement(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    seed_terms = (
        '设计',
        '开发',
        '生成',
        '驱动器',
        '电机',
        'pmsm',
        'bldc',
        '伺服',
        '吸尘器',
        '控制',
        '控制器',
        '控制系统',
        '环路',
        '电流环',
        '速度环',
        '位置环',
        '转矩环',
        'foc',
        'svpwm',
        'pid',
        'pi',
        '滑模',
        '弱磁',
    )
    return any(term in normalized for term in seed_terms)


def heuristic_route(text: str, state: dict) -> dict | None:
    program_generated = bool(state.get('program_generated'))
    load_curve_saved = bool(state.get('load_curve_saved'))
    metrics_ready = bool(state.get('metrics_ready'))
    tuning_started = bool(state.get('tuning_started'))
    ready_for_tuning = program_generated and load_curve_saved and metrics_ready

    if looks_like_generation_confirmation(text):
        return {'action': ACTION_CONFIRM_GENERATE, 'reason': '用户确认生成程序'}

    if looks_like_next_round_request(text):
        return {'action': ACTION_CONTINUE_NEXT_ROUND, 'reason': '用户要求继续下一轮仿真'}

    if looks_like_load_curve_request(text):
        return {'action': ACTION_SHOW_LOAD_CURVE, 'reason': '用户请求设置或重画负载曲线'}

    normalized = normalize_text(text)
    if ready_for_tuning and any(term in normalized for term in ('调优', '优化', '迭代参数', '重新跑', '重新运行')):
        return {'action': ACTION_START_TUNING, 'reason': '用户要求启动或重新启动调优'}

    if not program_generated:
        if looks_like_question(text) and not looks_like_program_revision(text) and not looks_like_metrics_request(text):
            return None
        if looks_like_program_revision(text) or looks_like_initial_program_requirement(text):
            return {'action': ACTION_REVISE_PROGRAM, 'reason': '用户提供了控制程序需求'}
        return {
            'action': ACTION_CLARIFY,
            'reply': '请描述原始应用场景或控制目标，例如吸尘器驱动、伺服位置控制、电流环控制或调速驱动。',
            'reason': '程序生成前输入不足以形成控制程序需求',
        }

    if looks_like_metrics_request(text):
        return {'action': ACTION_SUBMIT_METRICS, 'reason': '用户提供了性能指标或目标约束'}

    if looks_like_program_revision(text):
        return {'action': ACTION_REVISE_PROGRAM, 'reason': '用户修改控制程序需求'}

    if load_curve_saved and not metrics_ready and not looks_like_question(text):
        return {'action': ACTION_SUBMIT_METRICS, 'reason': '已保存负载曲线，当前输入更可能是指标需求'}

    if ready_for_tuning and looks_like_question(text):
        return None

    if ready_for_tuning and tuning_started:
        return None

    if ready_for_tuning:
        return {'action': ACTION_START_TUNING, 'reason': '三类信息已准备好'}

    return None


def build_router_user_prompt(text: str, state: dict, recent_history: list[dict]) -> str:
    history_lines = []
    for msg in recent_history[-8:]:
        role = msg.get('role', '')
        body = str(msg.get('text', '')).strip()
        if body:
            history_lines.append(f'{role}: {body}')

    payload = {
        'state': state,
        'recent_history': history_lines,
        'user_message': text,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_route_payload(raw_text: str) -> dict:
    content = (raw_text or '').strip()
    if content.startswith('```'):
        content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\s*```$', '', content)
    start = content.find('{')
    end = content.rfind('}')
    if start >= 0 and end >= start:
        content = content[start:end + 1]
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError('路由结果不是 JSON 对象')
    action = str(data.get('action') or '').strip()
    if action not in VALID_ACTIONS:
        raise ValueError(f'未知工作流动作：{action}')
    return {
        'action': action,
        'reply': str(data.get('reply') or '').strip(),
        'reason': str(data.get('reason') or '').strip(),
    }


class FlowRouteWorker(CancellableWorker):
    routed = pyqtSignal(dict)
    failure = pyqtSignal(str)

    def __init__(self, text: str, state: dict, recent_history: list[dict], parent=None):
        super().__init__(parent)
        self.text = text
        self.state = state
        self.recent_history = recent_history

    def run(self):
        try:
            user_prompt = build_router_user_prompt(self.text, self.state, self.recent_history)
            result = call_ui_chat_model(user_prompt, ROUTER_SYSTEM_PROMPT, temperature=0.0)
            if not self.cancelled:
                self.routed.emit(parse_route_payload(result))
        except Exception as exc:
            if not self.cancelled:
                self.failure.emit(str(exc))
