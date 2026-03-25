import os
import subprocess
import json
from openai import OpenAI
from pathlib import Path
import re
import time
import uuid
import threading

# Legacy prototype loop; package runtime is introduced under `deep_coder/`.
client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)


WORKDIR = Path.cwd()
SKILLDIR = WORKDIR / "skills"
TASKDIR = WORKDIR / ".tasks"
THRESHOLD = 128000
TRANSCRIPTDIR = WORKDIR / ".transcripts"
KEEPRECENT = 3
TEAMDIR = WORKDIR / ".team"
INBOXDIR = TEAMDIR / "inbox"

SYSTEM = f"""
    你是一个在目录 {os.getcwd()}. 使用bash脚本工具解决任务.输出内容务必保持为json格式，同时不要丢弃tool_call。
    
    你可以对复杂任务进行分解，然后创建任务；
    你可以通过将任务切分，然后将每个小任务提交给新的子智能体，需要注意，提交给子智能体的任务需要比较简单而且简短;

    技能(skills)列表：{SKILLDIR}
"""


SUBAGENT_SYSTEM = f"你是一个子智能体，在工作目录 {os.getcwd()}. 完成交给你的任务，然后总结你完成任务的摘要."


class BackgroundManager:
    def __init__(self):
        self.tasks = {}
        self._notification_queue = []
        self._lock = threading.Lock()

    def run(self, command: str) -> str:
        """
        开启一个后台任务，返回task_id
        """
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {"status": "running", "result": None, "command": command}
        thread = threading.Thread(
            target=self._execute, args=(task_id, command), daemon=True
        )
        thread.start()
        return f"后台任务 {task_id} 开始: {command[:80]}"
    
    def _execute(self, task_id: str, command: str) -> None:
        """
        运行子线程、获取线程输出、推送到队列
        """
        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=WORKDIR,
                capture_output=True,
                text=True,
                timeout=300
            )
            output = (r.stdout + r.stderr).strip()[:5000]
            status = "completed"
        except subprocess.TimeoutExpired:
            output = "错误：任务超时(300s)"
            status = "timeout"
        except Exception as e:
            output = "错误：{e}"
            status = "error"
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = output or "(no output)"
        with self._lock:
            self._notification_queue.append(
                {
                    "task_id": task_id,
                    "status": status,
                    "command": command,
                    "result": (output or "(no output)")
                }
            )
        
    def check(self, task_id: str = None) -> str:
        """
        检查一个任务的状态或者直接展示所有任务
        """

        # 检查一个任务
        if task_id:
            t = self.tasks.get(task_id)
            if not t:
                return f"错误：未知任务 {task_id}"
            return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or 'running'}"
        
        # 检查所有的任务
        lines = []
        for tid, t in self.tasks.items():
            lines.append(f"{tid}: [{t['status']}] {t['command'][:60]}")
        return "\n".join(lines) if lines else "没有后台任务"
    
    def drain_notification(self) -> list:
        """
        返回并清除所有待处理的完成通知。
        """
        with self._lock:
            notifs = list(self._notification_queue)
            self._notification_queue.clear()
        return notifs


# -- Layer 1: micro_compact - replace old tool results with placeholders --
def micro_compact(messages: list) -> list:
    """
    将工具调用产生的调用输出进行占位符压缩处理
    """

    # 忽略已经被占位符压缩的内容
    pattern = r'<compacted>.*?</compacted>'
    # 从消息中找出所有的工具调用的结果
    # 工具ID集合
    tool_id_group = set()
    # 工具调用列表
    tool_result = []
    for msg_idx, msg in enumerate(messages):
        if msg.get("role") == "tool" and not re.search(pattern, msg.get("content")):
            tool_id_group.add(msg.get("tool_call_id"))
            tool_result.append(msg_idx)
    
    # 如果工具调用数量小于 KEEPRECENT
    tool_count = len(tool_result)
    if tool_count <= KEEPRECENT:
        return messages
    
    # 将工具调用的结果进行压缩
    # 仅将工具执行结果进行全损的占位
    # 但依然可以通过上下文确定执行的命令以及对应参数
    for idx in range(tool_count - KEEPRECENT):
        content = messages[tool_result[idx]].get("content")
        # 如果调用结果小于100则保留
        if len(content) <= 100:
            continue
        messages[tool_result[idx]]["content"] = f"<compacted>tool_call_id: {messages[tool_result[idx]].get('tool_call_id')}</compacted>"
    return messages

# 自动摘要总结
def auto_compact(messages: list) -> list:
    """
    硬盘中存放所有的上下文
    """
    TRANSCRIPTDIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPTDIR / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    print(f"自动总结摘要，保存：{transcript_path}")

    # 将内容给LLM来进行总结摘要
    conversation_text = json.dumps(messages, default=str)
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "user",
                "content": "Summarize this conversation for continuity. Include: " +
                "1) What was accomplished, 2) Current state, 3) Key decisions made. " +
                "Be concise but preserve critical details.\n\n" + conversation_text,
            }
        ],
    )

    summary = response.choices[0].message.content
    return [
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from the summary. Continuing."}
    ]
    



class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills = {}
        self._load_all()
    
    def _load_all(self):
        if not self.skills_dir.exists():
            return 
        for f in sorted(self.skills_dir.rglob("SKILL.md")):
            text = f.read_text()
            meta, body = self._parse_frontmatter(text)
            name = meta.get("name", f.parent.name)
            self.skills[name] = {"meta": meta, "body": body, "path": str(f)}
        
    def _parse_frontmatter(self, text: str) -> tuple:
        """
        Parse YAML frontmatter between --- delimiters.
        """
        match = re.match(r"^---\n(.?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        meta = {}
        for line in match.group(1).strip().splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()
        return meta, match.group(2).strip()
    
    def get_descriptions(self) -> str:
        """
        Layer 1: short descriptions for the system prompt.
        """
        if not self.skills:
            return "(没有任何技能)"
        lines = []
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            tags = skill["meta"].get("tags", "")
            line = f"  - {name}: {desc}"
            if tags:
                line += f" [{tags}]"
            lines.append(line)
        return "\n".join(lines)
    
    def get_content(self, name: str) -> str:
        """
        Layer 2: full skill body returned in tool_result.
        """
        skill = self.skills.get(name)
        if not skill:
            return f"错误: 未知技能 '{name}'. 允许使用的技能: {', '.join(self.skills.keys())}"
        return f"<skill name = \"{name}\">\n{skill['body']}/n</skill>"

class TaskManager:
    def __init__(self, task_dir: Path):
        self.dir = task_dir
        self.dir.mkdir(exist_ok=True)
        self._next_id = self._max_id() + 1
    
    def _max_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0
    
    def _load(self, task_id: int) -> dict:
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"任务id: {task_id} 没有找到")
        return json.loads(path.read_text())
    
    def _save(self, task: dict):
        path = self.dir / f"task_{task['id']}.json"
        path.write_text(json.dumps(task, indent=2))
    
    def create(self, subject: str, description: str = "") -> str:
        task = {
            "id": self._next_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "blockedBy": [],
            "blocks": [],
            "owner": "",
        }
        self._save(task)
        self._next_id += 1
        return json.dumps(task, indent=2)
    
    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2)
    
    def update(self, task_id: int,
               status: str = None, 
               add_blocked_by: list = None,
               add_blocks: list = None) -> str:
        task = self._load(task_id)
        if status:
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"出现未知任务状态: {status}")
            task["status"] = status
            if status == "completed":
                self._clear_dependency(task_id)
        
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
        
        if add_blocks:
            task["blocks"] = list(set(task["blocks"] + add_blocks))

            for blocked_id in add_blocks:
                try:
                    blocked = self._load(blocked_id)
                    if task_id not in blocked["blockedBy"]:
                        blocked["blockedBy"].append(task_id)
                        self._save(blocked)
                except ValueError:
                    pass
        
        self._save(task)
        return json.dumps(task, indent=2)

    def _clear_dependency(self, completed_id: int):
        """
        Remove completed_id from all other tasks' blockedBy lists.
        """
        for f in self.dir.glob("task_*.json"):
            task = json.loads(f.read_text())
            if completed_id in task.get("blockedBy", []):
                task["blockedBy"].remove(completed_id)
                self._save(task)
    
    def list_all(self) -> str:
        tasks = []
        for f in sorted(self.dir.glob("task_*.json")):
            tasks.append(json.loads(f.read_text()))
        if not tasks:
            return "没有任何任务"
        
        lines = []
        for t in tasks:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]",
            }.get(t["status"], "[?]")
            blocked = f"此任务的前置阻塞任务：{t['blockedBy']}" if t.get("blockedBy") else "None"
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")
        return "\n".join(lines)

class TodoManager:
    def __init__(self):
        self.items = []
    
    def update(self, items: list) -> str:
        if len(items) > 20:
            raise ValueError("只允许最大20步计划") 
        validated = []
        in_progress_count = 0
        for i, item in enumerate(items):
            text = str(item.get("text", "")).strip()
            status = str(item.get("status", "pending")).lower()
            item_id = str(item.get("id", str(i + 1)))
            if not text:
                raise ValueError(f"条目 {item_id}: 需要文本描述")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"条目 {item_id}: 不合法状态 {status}")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({"id": item_id, "text": text, "status": status})
        if in_progress_count > 1:
            raise ValueError("同一时间只允许一个任务在运行")
        self.items = validated
        return self.render()

    def render(self) -> str:
        if not self.items:
            return "没有任务列表"
        lines = []
        for item in self.items:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}[item["status"]]
            lines.append(f"{marker} #{item['id']}: {item['text']}")
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")
        return "\n".join(lines)

# TODO = TodoManager()
TASK = TaskManager(TASKDIR)
SKILL_LOAD = SkillLoader(SKILLDIR)
BG = BackgroundManager()



def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"""Path esacapes workspace: {p}""")
    return path

def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "错误：出现高危命令"
    try:
        r = subprocess.run(command,
                           shell=True,
                           cwd=WORKDIR,
                           capture_output=True,
                           text=True,
                           timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out if len(out) else "(无输出，但工具调用成功)"
    except subprocess.TimeoutExpired:
        return "错误：命令执行超时"

def run_read(path: str, limit: int = None) -> str:
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit}) more lines"]
        return "\n".join(lines)[:5000]
    except Exception as e:
        return f"错误：{e}"

def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"写入 {len(content)} bytes to {path}"
    except Exception as e:
        return f"错误：{e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"错误：文本未找到 {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"修改：{path}"
    except Exception as e:
        return f"错误：{e}"

def run_subagent(prompt: str) -> str:
    sub_message = [{"role": "user", "content": prompt}]
    # 固定限制
    for _ in range(30):
        response = client.chat.completions.create(
            model="deepseek-chat",
            tools=CHILD_TOOLS,
            messages=[
                {"role": "system", "content": SUBAGENT_SYSTEM},
                *sub_message,
            ],
        )

        # 获取消息
        content = response.choices[0].message.content
        # 工具信息
        tool_call = response.choices[0].message.tool_calls
        if content:
            print(f"\033[32m subagent: {content} \033[0m")
        assistant_message = {
            "role": "assistant",
            "content": content or "",
        }
        if tool_call:
            assistant_message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in tool_call
            ]
        sub_message.append(assistant_message)

        if tool_call is None:
            break

        for tool in tool_call:
            # 工具选择
            tool_handler = TOOL_HANDLER[tool.function.name]
            # 工具参数加载
            tool_args = json.loads(tool.function.arguments)

            print(f"""\033[32m subagent: $ {tool.function.name} \033[0m""")
            
            # 工具执行
            try:
                output = tool_handler(**tool_args) if tool_handler else f"未知工具: {tool.function.name}"
            except Exception as e:
                output = f"错误：{e}"
            
            print(f"""{output[:200]}""")
            sub_message.append({"role": "tool", "tool_call_id": tool.id, "content": output})
        
    return "".join(response.choices[0].message.content if response.choices[0].message.content else "(没有摘要)")


TOOL_HANDLER = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    # "todo": lambda **kw: TODO.update(kw["items"]),
    "task": lambda **kw: run_subagent(kw["prompt"]),
    "load_skill": lambda **kw: SKILL_LOAD.get_content(kw["name"]),
    "task_create": lambda **kw: TASK.create(kw["subject"], kw.get("description", "")),
    "task_update": lambda **kw: TASK.update(kw["task_id"], kw.get("status"), kw.get("addBlockedBy"), kw.get("addBlocks")),
    "task_list": lambda **kw: TASK.list_all(),
    "task_get": lambda **kw: TASK.get(kw["task_id"]),
    "compact": lambda **kw: "摘要总结",
    "background_run": lambda **kw: BG.run(kw["command"]),
    "check_background": lambda **kw: BG.check(kw.get("task_id")),
}

CHILD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "将传递进来的bash命令运行",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "单条命令，例如创建一个aa目录，mkdir aa。"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "阅读文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "限制长度"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "向文件内写入内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "写入文件的内容"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "替换文件中存在的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "旧的文本内容"
                    },
                    "new_text": {
                        "type": "string",
                        "description": "新的文本内容"
                    }
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": "根据技能名字加载对应的特殊知识",
            "parameters":{
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "需要加载的技能名字，例如：python_skill"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "background_run",
            "description": "在后台线程中运行命令。立即返回task_id。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "需要在后台中运行的命令"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_background",
            "description": "检查后台任务状态。省略task_id可列出所有任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "任务ID",
                        }
                    }
                }
            }
        }
    },
]

PARENT_TOOLS = CHILD_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "task_create",
            "description": "创建一个新任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "任务的主题"
                    },
                    "description": {
                        "type": "string",
                        "description": "任务描述"
                    }
                }
            },
            "required": ["subject"]
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_update",
            "description": "更新任务的状态以及对应的前置依赖任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "任务ID"
                    },
                    "status": {
                        "type": "string",
                        "enum": [
                            "pending",
                            "in_progress",
                            "completed"
                        ],
                        "description": "任务状态"
                    },
                    "addBlockedBy": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        },
                        "description": "需要增加的前置依赖"
                    },
                    "addBlocks": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        },
                        "description": "需要增加的后置依赖"
                    },
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_list",
            "description": "列出所有的任务以及状态摘要",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_get",
            "description": "通过任务ID来获取此任务的所有细节",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "任务ID",
                    }
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compact",
            "description": "标识当前的对话历史是否需要进行摘要总结",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "摘要总结中什么是重要的"
                    }
                }
            }
        }
    },
]


def agentLoop(message: list):

    # 规划步数
    round_todo = 0

    while True:

        # 清空后台完成的命令，并将结果注入到message中
        notifs = BG.drain_notification()
        if notifs and message:
            notif_text = "\n".join(
                f"[bg: {n['task_id']} {n['status']}: {n['result']}]" for n in notifs
            )
            message.append({"role": "user", "content": f"<background>\n{notif_text}\n</background>"})
            message.append({"role": "assistant", "content": "注意后台任务结果"})

        # 第一层，调用工具结果压缩
        # micro_compact(message)

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM},
                *message,
            ],
            model="deepseek-chat",
            tools=PARENT_TOOLS,
        )

        print(f"\033[31m recent token useage: {response.usage.total_tokens} cache hit: {response.usage.prompt_cache_hit_tokens} cache miss: {response.usage.prompt_cache_miss_tokens} \33[0m")

        # 第二层，根据token用量来确定是否进行auto_compact
        if response.usage.total_tokens >= THRESHOLD:
            print("\033[32m [auto compact triggered] \033[0m")
            message = auto_compact(message)

        # print(f"""\033[33m token useage: {response.usage.completion_tokens.real} \033[0m""")

        content = response.choices[0].message.content
        tool_call = response.choices[0].message.tool_calls

        if content:
            print(f"""\033[33m{content}\033[0m""")
        
        assistant_message = {
            "role": "assistant",
            "content": content or "",
        }

        if tool_call:
            assistant_message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_call
            ]
        message.append(assistant_message)


        # 如果没有发生工具调用
        if tool_call is None:
            break
        
        used_todo = False
        need_compact = False
        for tool in tool_call:
            # 确定是否需要自动摘要
            need_compact = True if tool.function.name == "compact" else need_compact
            # 工具选择
            tool_handler = TOOL_HANDLER[tool.function.name] 
            # 工具参数加载
            tool_args = json.loads(tool.function.arguments)
            print(f"""\033[33m$ {tool.function.name} \033[0m""")
            # 工具执行
            try:
                output = tool_handler(**tool_args) if tool_handler else f"未知工具: {tool.function.name}"
            except Exception as e:
                output = f"错误: {e}"
            print(f"""{output[:200]}""")
            message.append({"role": "tool", "tool_call_id": tool.id, "content": output})
            # 如果是todo工具
            # 待办事项表更新
            if tool.function.name == "todo":
                used_todo = True

        round_todo = 0 if used_todo else round_todo + 1
        if round_todo >= 3:
            message.append({"role": "user", "content": "根据历史上下文，更新你的待办事项列表"})
            
        if need_compact:
            print("\033[32m [manual compact triggered] \033[0m")
            message = auto_compact(message)
            
        

if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agentLoop(history)
        print()
