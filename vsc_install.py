import os
import platform
import requests
import zipfile
import shutil
import subprocess

tag = '🍎🍎🍎 Local Robot Environment Builder 🍎'
def find_vscode_download(platform):
    """Finds the appropriate VS Code download URL for the given platform.

    Args:
        platform: The platform string (e.g., 'Windows', 'macOS', 'Linux').

    Returns:
        str: The download URL for VS Code.
    """
    if platform not in ["Windows", "macOS", "Linux", "Darwin"]:
        print(f'\n\n{tag} 👿👿👿 Invalid platform: {platform}')
        raise ValueError(f"Invalid platform: {platform}")

    print(f"{tag} Finding VS Code download URL for platform: {platform}")   
    base_url = "https://code.visualstudio.com/sha/download?build=stable&os="
    platform_suffixes = {
        "Windows": "win32-x64-user",
        "macOS": "darwin-arm64-user",
        "Linux": "linux-x64-user",
    }
    suffix = platform_suffixes.get(platform)
    download_url = f"{base_url}{suffix}"
    print(f"{tag} VS Code download URL: {download_url}")    
    return download_url


def download_and_extract(download_url, output_dir):
    """Downloads the VS Code installer and extracts it to the specified directory.

    Args:
        download_url: The URL to download VS Code from.
        output_dir: The directory to extract the installer to.
    """
    print(f"\n{tag} Downloading VS Code installer...")
    try:
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        with zipfile.ZipFile(response.raw) as zip_ref:
            zip_ref.extractall(output_dir)

        print(f"{tag} VS Code installer downloaded and extracted to  🥦 {output_dir}")
    except Exception as e:
        print(f"{tag} Error downloading VS Code: {e}")


def install_vscode(output_dir):
    """Installs VS Code from the extracted installer.

    Args:
        output_dir: The directory containing the extracted installer.
    """

    print(f"\n{tag} Installing VS Code...")
    installer_path = os.path.join(output_dir, "VSCode-win32-x64-user.exe")
    if platform.system() == "Darwin":
        installer_path = os.path.join(output_dir, "VSCode-darwin-arm64-user.zip")
    elif platform.system() == "Linux":
        installer_path = os.path.join(output_dir, "VSCode-linux-x64-user.tar.gz")

    print(f"{tag} VS Code installer path: {installer_path}")

    try:
        if platform.system() == "Windows":
            subprocess.run([installer_path], shell=True)
        elif platform.system() == "Darwin":
            with zipfile.ZipFile(installer_path, "r") as zip_ref:
                zip_ref.extractall(output_dir)
            shutil.move(
                os.path.join(output_dir, "VSCode-darwin-arm64-user"), "/Applications"
            )
        elif platform.system() == "Linux":
            subprocess.run(["tar", "-xzf", installer_path, "-C", output_dir], shell=True)

        print(f"{tag} VS Code installed successfully.")
    except Exception as e:
        print(f"\n\n{tag} 👿👿👿 Error installing VS Code: {e} 👿\n")


def install_vscode_extensions(extensions, vscode_path):
    """Installs VS Code extensions using the command line.

    Args:
        extensions: A list of extension IDs to install.
        vscode_path: The path to the VS Code executable.
    """
    print(f"{tag} Installing extensions: {extensions}")
    for extension in extensions:
        command = [vscode_path, "--install-extension", extension]
        subprocess.run(command, shell=True)
    print(f"{tag} VS Code extensions installed successfully.")
def create_vscode_project(source_folder, project_name, vscode_path):
    """Copies a folder from the machine and creates a VS Code project.

    Args:
        source_folder: The path to the folder to copy.
        project_name: The name of the VS Code project.
        vscode_path: The path to the VS Code executable.
    """
    print(f"{tag} Creating VS Code project '{project_name}'...")

    # Create the project directory
    project_dir = os.path.join(os.getcwd(), project_name)
    os.makedirs(project_dir, exist_ok=True)

    # Copy the source folder to the project directory
    print(f"{tag} Copying folder '{source_folder}' to '{project_dir}'...")
    shutil.copytree(source_folder, project_dir, dirs_exist_ok=True)

    # Open the project in VS Code
    print(f"{tag} Opening project '{project_name}' in VS Code...")
    subprocess.run([vscode_path, project_dir], shell=True)

    print(f"{tag} VS Code project created successfully!")


def start_installation(project_source_folder:str):
    """Main function to find, download, extract, install VS Code, and install extensions."""
    print(f"\n\n{tag} Installing VS Code and extensions. project source folder: {project_source_folder}\n")

    current_platform = platform.system()
    print(f"{tag} Current platform: {current_platform}")
    if current_platform == None:
        print(f'{tag} we are fucked, Boss! - no platform found')
        raise ValueError(f"{tag} 👿👿👿 Invalid platform: {current_platform}")

    download_url = find_vscode_download(current_platform)
    temp_dir = os.path.join(os.path.expanduser("~"), "Downloads", "vscode_temp")
    os.makedirs(temp_dir, exist_ok=True)
    download_and_extract(download_url, temp_dir)
    install_vscode(temp_dir)

    # Get the VS Code executable path
    vscode_path = os.path.join(temp_dir, "VSCode-win32-x64-user.exe")
    if platform.system() == "Darwin":
        vscode_path = os.path.join(
            "/Applications", "VSCode.app", "Contents", "MacOS", "VSCode"
        )
    elif platform.system() == "Linux":
        vscode_path = os.path.join(temp_dir, "VSCode-linux-x64-user", "bin", "code")
    print(f"{tag} VS Code executable path: {vscode_path}")

    # Define the extensions to install
    extensions_to_install = [
        "ms-python.python",
        "ms-vscode-remote.remote-ssh",
        "robocorp.robocorp-code",
    ]
    print(f"{tag} extensions to install: {extensions_to_install}")

    # Install the extensions
    install_vscode_extensions(extensions_to_install, vscode_path)
    print(f"{tag} VS Code extensions installed successfully.")

    shutil.rmtree(temp_dir)
    print(f"{tag} VS Code and extensions installed successfully.")

    create_vscode_project(project_name='ReconRobot', vscode_path=vscode_path, source_folder='ReconRobot')

    print(f"\n\n{tag}  🥬 🥬 🥬 VS Code project created successfully!  🥬 🥬 🥬\n\n")


# Installs an environment to enable running a production robot locally on a customer's machine
source_folder = "/Users/aubreymalabie/Work/liza-work/tiger-robot"
project_name = "ReconRobot"

start_installation(project_source_folder=source_folder)
