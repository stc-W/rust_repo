import subprocess
import pandas as pd
import os
def clone_repositories(repo_list, target_directory):
    for repo in repo_list:
        repo_name = repo.split("/")[-1].replace(".git", "")
        target_path = f"{target_directory}/{repo_name}"
        if not os.path.isdir(target_path):
            print(f"Cloning {repo} into {target_path}...")
            subprocess.run(["git", "clone", repo, target_path], check=True)
def download_repo():
    df = pd.read_csv("cve_with_issue_and_commit.csv")
    complete = df[df["status"] == "完成"]
    repos = set(complete["repo_url"])
    clone_repositories(repo_list=repos, target_directory="./lib")


download_repo()
        