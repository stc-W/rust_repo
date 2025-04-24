import json
import re
import subprocess
import requests

def chat(messages, model, json_format=False, options={"num_ctx": 131072}):
    url = "http://localhost:11434/api/chat"
    data = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options
    }
    if json_format:
        data["format"] = "json"
    timeout = 10000
    try:
        res = requests.post(url, json=data, timeout=timeout)
        s = json.loads(res.text)["message"]["content"]
        return s
    except requests.exceptions.Timeout:
        print("time out")
        return "err"
    except Exception:
        return "err"


def get_prompt(project, crate, issue, commit):
    prompt = f'''You are given information about a Rust project and a bug-related issue with its corresponding commit. Your task is to help extract the test code that triggers the bug, and then construct a standalone, runnable main function in Rust that reproduces the bug behavior.

    Project Information:
    Project name: {project}

    Crate name: {crate}

    Issue details: {issue}

    Commit log details: {commit}

    Task Description:
    Extract the test code that triggers the bug. This code may appear:

    In the Rust issue description or discussion; or

    In the test files added or modified in the bug-fixing commit (typically regression tests).

    Construct a minimal, standalone main.rs file that includes:

    The necessary imports and crate declarations;

    The bug-triggering logic adapted from the test;

    Any mocked data or simplified setup needed to run independently;

    A main() function that compiles and executes the bug trigger.

    Requirements:
    Output only valid Rust code.

    Ensure the generated code can compile .

    If any part of the logic is unclear or incomplete, you may add comments or TODOs indicating assumptions.'''
    return prompt

def extract_issue_info(issue_url: str):
    """
    从 GitHub issue URL 中直接使用 split 提取 owner、repo 和 issue_number。
    示例：https://github.com/owner/repo/issues/123
    """
    if issue_url.__contains__(","):
        issue_url = issue_url.split(",")[0]
    parts = issue_url.strip().split("/")
    
    if len(parts) < 5 or parts[-2] != "issues":
        raise ValueError("❌ URL 格式错误，应为 https://github.com/owner/repo/issues/123")
    if parts[6].__contains__("#"):
        parts[6] = parts[6].split["#"][0]
    return parts[3], parts[4], int(parts[6])
    
def get_issue(issue_url):
    
    token = "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"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    owner, repo, issue_number = extract_issue_info(issue_url=issue_url)
    # 获取 issue 信息
    issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    issue = requests.get(issue_url, headers=headers).json()
    # 获取评论信息
    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    comments = requests.get(comments_url, headers=headers).json()
    lines = []
    lines.append(f"Title: {issue['title']}")
    lines.append(f"Body: {issue['body']}")
    lines.append("\n--- Comments ---")

    for comment in comments:
        username = comment["user"]["login"]
        body = comment["body"]
        lines.append(f"{username} said:")
        lines.append(body)
        lines.append("---")
    return "\n".join(lines)

def get_added_lines_from_commit(commit_hash: str, lib: str) -> str:
    """
    获取指定 commit 中所有新增（以 '+' 开头，排除 diff 元信息）的代码行。
    """
    result = subprocess.run(
        ["git", "show", commit_hash],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        cwd=f"./lib/{lib}"
    )

    if result.returncode != 0:
        raise RuntimeError(f"Git show failed: {result.stderr}")
        
    added_lines = []
    for line in result.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])  # 去掉前缀的 '+'

    return "\n".join(added_lines)


def get_response(issue_url, lib, crate, commit_hash):
    issue_messages = get_issue(issue_url)
    commit_message = get_added_lines_from_commit(commit_hash=commit_hash, lib=lib)
    final_prompt = get_prompt(project=lib, crate=crate, issue=issue_messages, commit=commit_message)
    messages = [{"role": "user", "content": final_prompt}]
    answer = chat(messages=messages, model="qwen2.5:32b")
    pattern = r'```rust\n(.*?)```'
    # 使用 re.DOTALL 使 . 匹配包括换行符在内的所有字符
    java_code_blocks = re.findall(pattern, answer, re.DOTALL)
    if len(java_code_blocks) > 0:
        return java_code_blocks[0]
    else:
        return None