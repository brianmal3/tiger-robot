import subprocess
import time


tag = "🍎🍎🍎 The Robot Runner 🍎"
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../")
def run_command(command):

    """Runs a terminal command and checks for successful execution.

    Args:
        command: The command to execute as a string.

    Returns:
        True if the command executed successfully, False otherwise.
    """

    start_time = time.time()
    print(f"{tag} Running command:  🔵 {command}  🔵")
    process = subprocess.run(command, shell=True, capture_output=True, text=True)
    elapsed_time = time.time() - start_time

    global total_elapsed_seconds  # Tell the function to use the global variable
    total_elapsed_seconds += elapsed_time  # Use the += operator for clarity

    # Check if the command executed successfully
    if process.returncode == 0:
        print(
            f"{tag} Command executed successfully. 🥬 Elapsed time: 🌼 {elapsed_time:.2f} seconds\n"
        )
        return True
    else:
        print(
            f"{tag} Error: 👿👿👿 Command failed with return code {process.returncode}.\n"
        )
        print(f"{tag} Error: {process.stderr}\n")
        return False

    COMMAND = """ /usr/bin/env /var/folders/xg/dm5xlygj10n4b2pkmmkwhdpw0000gn/T/rf-ls-run/run_env_00_pddxx6fv.sh /Users/aubreymalabie/.vscode/extensions/robocorp.robocorp-code-1.22.3-darwin-arm64/bin/rcc task run --robot /Users/aubreymalabie/Work/liza-work/tiger-robot/robot.yaml --space vscode-03 --workspace e5176ebb-dd4d-467f-b716-24fa52393e8c --account robocorp-code --task Run\ Task --controller RobocorpCode """
