import os
import shutil
import subprocess
from cybergym import Agent

# Determine the directory where main.py resides
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class SWEAgent(Agent):
    def __init__(self, input):
        super().__init__(True)
        self._tasks = []
        self._results = []

        # Determine if Docker is running in rootless mode and configure accordingly
        try:
            security_options = subprocess.check_output(
                ["docker", "info", "--format", "{{.SecurityOptions}}"]
            ).decode().lower()
            if "rootless" in security_options:
                os.environ["DOCKER_HOST"] = f'unix:///run/user/{os.getuid()}/docker.sock'
        except Exception as e:
            print("Warning: Could not determine Docker mode, defaulting to root mode.")

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

        # Use current working directory for benchmark location
        benchmark_base = os.path.join(os.getcwd(), "benchmark", "arvo")
        os.makedirs(benchmark_base, exist_ok=True)

        for task in input:
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
            
            # Replace all occurrences of '##ARVO_ID##' with the task id in specified files
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
            # Use current working directory for benchmark location
            dest_dir = os.path.join(os.getcwd(), "benchmark", "arvo", task_id)
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
                env = os.environ.copy()
                env["PYTEST_CURRENT_TEST"] = "1"
                subprocess.check_call(cmd, cwd=BASE_DIR, env=env)
                print(f"Task {task_id} completed successfully.")
            except subprocess.CalledProcessError as error:
                print(f"Error during task {task_id}: {error}")
            finally:
                container_name = f"cybergym-sweagent-{task_id}"
                try:
                    subprocess.check_call(["docker", "rm", "-f", container_name])
                    print(f"Container {container_name} removed successfully.")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to remove container {container_name}: {e}")
    
    def get_results(self):
        pass