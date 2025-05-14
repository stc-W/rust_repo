
import re
import subprocess
import llm_util
code_generate_model = "qwen2.5-coder:32b"

def compile_code(src_path):
    try:
        # 调用 javac 编译 Java 代码
        subprocess.run( 
            ["cargo", "check", "--tests"],
            check=True,
            capture_output=True,
            text=True,
            cwd=src_path
        )
        return 0, f"compile success: {src_path}"
    except subprocess.CalledProcessError as e:
        return 1, f'''compile fail{e.stderr.split("error")[1]}'''

def get_generate_prompt(function):
    prompt = f'''You are a skilled Rust developer. Please write comprehensive unit tests for the following Rust function.
    Requirements:
    Wrap all test code in a #[cfg(test)] mod tests block.
    Provide multiple test cases, each marked with #[test].
    If the function contains unsafe blocks:
    Write tests that exercise the unsafe paths as thoroughly as possible.
    Ensure the tests themselves remain safe unless unsafe is absolutely required.
    If the function does not contain unsafe code:
    Ensure the tests provide full logic coverage, including edge cases and error handling.
    The tests should be concise, readable, and reflect realistic use cases.
    Do not rewrite or modify the original function, only generate the test code.
    Here's the function and its context:
    ```
    rust
    // Function and context go here
    {function}
    ```
    Please generate only the test code according to the above requirements.'''
    return prompt

def get_repair_prompt(function, error_message):
    prompt = f'''
    You previously generated some Rust unit test code for me, but it fails to compile.↳

    Now, I will provide you with:

    The Rust test code you wrote

    The exact compiler error messages produced by rustc or cargo test

    Please help me analyze the compiler errors and modify your test code accordingly so that:

    The code successfully compiles and runs;

    The tests still aim to provide maximum coverage, especially of any unsafe blocks if they exist;

    You do not change the original function itself — only fix and improve the test code;

    If the error is due to missing context or types, please suggest minimal code additions that are needed to make the test compile;

    Ensure your revised code is idiomatic and adheres to best practices in Rust unit testing.

    Here is the current test code:
    ```
    rust
    {function}
    ```
    And here are the compiler errors:

    ```
    error
    {error_message}
    ```
    Please provide the corrected test code only.'''
def repair_code(code, error_message, src_path):
    prompt = get_repair_prompt(code, error_message)
    messages = [{"role": "user", "content": prompt}]
    rust_code = llm_util.chat(messages=messages, model=code_generate_model)
    pattern = r'```rust\n(.*?)```'
    rust_code_blocks = re.findall(pattern, rust_code, re.DOTALL)
    if len(rust_code_blocks) <= 0:
        return None 
    with open (f"{src_path}/src/main.rs", "w") as f:
        f.write(rust_code_blocks[0])
        f.flush()
        f.close()
    tag, error_message = compile_code(src_path)
    cnt = 0
    while tag == 1 and cnt <= 3:
        code = rust_code_blocks[0]
        prompt = get_repair_prompt(code, error_message)
        messages = [{"role": "user", "content": prompt}]
        rust_code = llm_util.chat(messages=messages, model=code_generate_model)
        pattern = r'```rust\n(.*?)```'
        rust_code_blocks = re.findall(pattern, rust_code, re.DOTALL)
        if len(rust_code_blocks) <= 0:
            return None 
        with open (f"{src_path}/src/main.rs", "w") as f:
            f.write(rust_code_blocks[0])
            f.flush()
            f.close()
        tag, error_message = compile_code(src_path)
    if tag == 0:
        return None
    else:
        return 0
def generate_code(function, src_path):
    generation_code = get_generate_prompt(function)
    messages = [{"role": "user", "content": generation_code}]
    rust_code = llm_util.chat(messages=messages, model=code_generate_model)
    pattern = r'```rust\n(.*?)```'
    rust_code_blocks = re.findall(pattern, rust_code, re.DOTALL)
    if len(rust_code_blocks) <= 0:
        return None 
    with open(f"{src_path}\src\main.rs", "w") as f:
        f.write(rust_code_blocks[0])
        f.flush()
        f.close()
    tag, error = compile_code(src_path)
    if tag == 0:
        return 0
    else:
        t = repair_code(rust_code_blocks[0], error, src_path)
        return t


