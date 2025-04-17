import os
import shutil
import subprocess
from cybergym import get_dataset, Agent

# Determine the directory where main.py resides
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class SWEAgent(Agent):
    def __init__(self, task_list):
        super().__init__(True)
        self._tasks = []
        self._results = []
        
        # Load the dataset
        ds = get_dataset(task_list)

        # Pull the latest Docker image
        subprocess.check_call(["docker", "pull", "sweagent/enigma:latest"])

        # Create ctfnet network
        try:
            subprocess.check_output(["docker", "network", "inspect", "ctfnet"])
        except subprocess.CalledProcessError:
            subprocess.check_call(["docker", "network", "create", "ctfnet"])

        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            with open(os.path.join(BASE_DIR, "keys.cfg"), "w") as key_file:
                key_file.write(f"OPENAI_API_KEY: '{api_key}'")
        else:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")

        benchmark_base = os.path.join(BASE_DIR, "benchmark", "arvo")
        os.makedirs(benchmark_base, exist_ok=True)

        for task in ds:

            self._tasks.append(task)

            task_id = task["id"]
            # Destination directory for the current task
            dest_dir = os.path.join(benchmark_base, task_id)
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)
            # Copy the template directory relative to this file
            template_dir = os.path.join(BASE_DIR, "nyuctf-template")
            shutil.copytree(template_dir, dest_dir)
            
            # Copy additional files to the task's files folder
            files_dest = os.path.join(dest_dir, "files")
            os.makedirs(files_dest, exist_ok=True)
            for file_path in task["files"]:
                if os.path.isfile(file_path):
                    shutil.copy2(file_path, files_dest)
            
            # Replace all occurrences of '##ARVO_ID##' with the task id in docker-compose.yml and metadata/metadata.json
            file_paths = [
                os.path.join(dest_dir, "docker-compose.yml"),
                os.path.join(dest_dir, "challenge.json"),
                os.path.join(dest_dir, "files", "README"),
                os.path.join(dest_dir, "flag.txt")
            ]
            for file_path in file_paths:
                if os.path.isfile(file_path):
                    with open(file_path, "r") as f:
                        content = f.read()
                    content = content.replace("##ARVO_ID##", task_id)
                    with open(file_path, "w") as f:
                        f.write(content)

    def run(self):
        for task in self._tasks:
            task_id = task["id"]
            print(f"Running task {task_id}...")
            dest_dir = os.path.join(BASE_DIR, "benchmark", "arvo", task_id)
            try:
                cmd = [
                    "python", "run.py",
                    "--model_name", "gpt4",
                    "--ctf",
                    "--image_name", "sweagent/enigma:latest",
                    "--data_path", os.path.join(dest_dir, "challenge.json"),
                    "--repo_path", dest_dir,
                    "--config_file", "config/default_ctf.yaml",
                    "--per_instance_cost_limit", "2.00"
                ]
                subprocess.check_call(cmd, cwd=BASE_DIR)
                print(f"Task {task_id} completed successfully.")
            except subprocess.CalledProcessError as error:
                print(f"Error during task {task_id}: {error}")
    
    def get_results(self):
        pass