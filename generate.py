import os
import shutil
import subprocess
import pandas as pd
from packaging import version
import toml
from extractor import get_response
from util import download_repo
df = pd.read_csv("cve_with_issue_and_commit.csv")

edition = {
    "2015": "1.0",
    "2018": "1.31.0",
    "2021": "1.56.0",
    "2024": "1.85.0"
}
complete = df[df["status"] == "完成"]
def install_all_require_rust_toolchain():
    version_set = set()
    for key, value in edition.items():
        version_set.add(value)
    for data in complete.itertuples():
        print(data)
        if not pd.isna(data.std_version):
            version_set.add(data.std_version)
    print(version_set)
    for version in version_set:
        print(f"Installing Rust {version}...")
        result = subprocess.run(["rustup", "install", version], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Rust {version} installed successfully.")
        else:
            print(f"❌ Failed to install Rust {version}.")
            print("Error message:", result.stderr)

def from_version_get_edition(rust_version):
    v = version.parse(rust_version)
    if v >= version.parse("1.85.0"):
        return 2024
    elif v >= version.parse("1.56.0"):
        return 2021
    elif v >= version.parse("1.31.0"):
        return 2018
    else:
        return 2015
    
def get_earliest_parent(commit_hash, lib):
    path = f"./lib/{lib}"
    # 获取所有父 commit
    parents = subprocess.run(
        ['git', 'log', '-1', '--pretty=%P', commit_hash],
        capture_output=True, text=True, cwd=path
    ).stdout.strip().split()

    if len(parents) == 0:
        return None  # 无父（根 commit）

    if len(parents) == 1:
        return parents[0]  # 只有一个父，就返回它

    # 多个父，找最早的那个
    timestamps = []
    for parent in parents:
        timestamp = subprocess.run(
            ['git', 'log', '-1', '--pretty=%ct', parent],
            capture_output=True, text=True, cwd=path
        ).stdout.strip()
        timestamps.append((int(timestamp), parent))

    timestamps.sort()
    return timestamps[0][1]

def get_crates_name(lib):
    with open(f"./lib/{lib}/Cargo.toml", "r") as ff:
        t = toml.load(ff)
    try:
        return t["package"]["name"]
    except Exception as e:
        return None
download_repo()
# install_all_require_rust_toolchain()
for index, row in complete.iterrows():
    if not pd.isna(row["edition"]):
        complete.at[index, "edition"] = str(complete.at[index, "edition"]).split(".")[0]

for index, row in complete.iterrows():
    if pd.isna(row["edition"]) and pd.isna(row["std_version"]):
        complete.at[index, "edition"] = "2021"
        complete.at[index, "std_version"] = "1.85.0"
    elif pd.isna(row["edition"]):
        complete.at[index, "edition"] = from_version_get_edition(row["std_version"])    
    elif pd.isna(row["std_version"]):
        complete.at[index, "std_version"] = edition[row["edition"]]

failed_list = []

for index, row in complete.iterrows():
    # Save the rust projects to the "dataset" directory
    if not os.path.exists("dataset"):
        os.makedirs("dataset")
    dataset_path = "dataset"

    try:
        cve_id = row["cve_id"]
        edition = row["edition"]
        lib = row["repo_url"].split("/")[-1]
        repo_url = row["repo_url"]
        repair_hash = row["commits_sha"]
        name = get_crates_name(lib)
        
        if os.path.exists(f"{dataset_path}/{cve_id}_repair"):
            print(f"Project {cve_id}已经存在, 跳过")
            continue
        
        if name is None:
            print(f"❌ cve_id: {cve_id}, lib: {lib}有问题, 查询不到包名")
            continue
        
        
        if pd.isna(row["commits_sha_begin"]):
            bug_hash = get_earliest_parent(repair_hash, lib)
        else:     
            bug_hash = get_earliest_parent(row["commits_sha_begin"], lib)
        result1 = subprocess.run(["cargo", "new", f"{cve_id}_repair", "--edition", str(edition)], capture_output=True, text=True, cwd=dataset_path)
        if result1.returncode == 0:
            print(f"✅ Project {cve_id}_repair created successfully.")
        else:
            print(f"❌ Failed to create Rust project {cve_id}.")
            print("Error message:", result1.stderr)
            continue
        result2 = subprocess.run(["cargo", "new", f"{cve_id}_bug", "--edition", str(edition)], capture_output=True, text=True, cwd=dataset_path)
        
        if result2.returncode == 0:
            print(f"✅ Project {cve_id}_bug created successfully.")
        else:
            print(f"❌ Failed to create Rust project {cve_id}.")
            print("Error message:", result2.stderr)
            
        with open(f"./{dataset_path}/{cve_id}_repair/rust-toolchain.toml", "w") as f1:
            f1.write(f'''[toolchain]\nchannel = "{row["std_version"]}"''')
            f1.flush()
            f1.close()
        with open(f"./{dataset_path}/{cve_id}_bug/rust-toolchain.toml", "w") as f2:
            f2.write(f'''[toolchain]\nchannel = "{row["std_version"]}"''')
            f2.flush()
            f2.close()
        with open(f"./{dataset_path}/{cve_id}_repair/Cargo.toml", "a") as f3:
            f3.write(f'''{name} = {{git = "{repo_url}", rev = "{repair_hash}"}}''')
            f3.flush()
            f3.close()
        with open(f"./{dataset_path}/{cve_id}_bug/Cargo.toml", "a") as f4:
            f4.write(f'''{name} = {{git = "{repo_url}", rev = "{bug_hash}"}}''')
            f4.flush()
            f4.close()
            
        rust_code = get_response(issue_url=row["issues"], lib=lib, crate=name, commit_hash=repair_hash)
        if rust_code is not None:
            with open(f"./{dataset_path}/{cve_id}_repair/src/main.rs", "w") as f5:
                f5.write(rust_code)
                f5.flush()
                f5.close()
            with open(f"./{dataset_path}/{cve_id}_bug/src/main.rs", "w") as f6:
                f6.write(rust_code)
                f6.flush()
                f6.close()    
        print(f"✅ Project {cve_id} 填充完成.")
    except Exception as e:
        path1 = f"./{dataset_path}/{cve_id}_repair/"
        path2 = f"./{dataset_path}/{cve_id}_bug/"        
        if os.path.exists(path1):
            shutil.rmtree(path1)
        if os.path.exists(path2):
            shutil.rmtree(path2)
        print(f"❌ Project {cve_id} 填充失败.")
        print(f"Err message: {e}")
        failed_list.append(cve_id)
        
with open("failed_list.txt", "w") as f:
    for item in failed_list:
        f.write(f"{item}\n")
        f.flush()
        f.close()

   
        
# print(complete)


