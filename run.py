import os
import shutil
import xml.etree.ElementTree as ET
import subprocess

# Path to your manifest file
MANIFEST_FILE = "manifest.xml"  # Replace with the correct path if needed


def setup_sparse_checkout(path, sparse_paths):
    subprocess.run(["git", "-C", path, "config", "core.sparseCheckout", "true"], check=True)
    sparse_file = os.path.join(path, ".git", "info", "sparse-checkout")
    with open(sparse_file, "w") as f:
        for sparse_path in sparse_paths:
            f.write(sparse_path.rstrip("/") + "/*\n")
    print(f"Sparse-checkout paths configured: {sparse_paths}")


def move_files_to_parent(path, sparse_path):
    target_folder = os.path.join(path, sparse_path.rstrip("/"))
    if os.path.exists(target_folder) and os.path.isdir(target_folder):
        for file_name in os.listdir(target_folder):
            src_file = os.path.join(target_folder, file_name)
            dst_file = os.path.join(path, file_name)
            print(f"Moving {src_file} to {dst_file}...")
            shutil.move(src_file, dst_file)
        print(f"Removing folder: {target_folder}")
        shutil.rmtree(target_folder)


def clone_repo(name, remote_url, path, revision, sparse_paths=None):
    if not os.path.exists(path):
        print(f"Cloning {name} into {path}...")
        subprocess.run(["git", "clone", "--no-checkout", remote_url, path], check=True)
    else:
        print(f"{name} already exists at {path}. Pulling latest changes...")
        subprocess.run(["git", "-C", path, "fetch"], check=True)

    if sparse_paths:
        setup_sparse_checkout(path, sparse_paths)

    print(f"Checking out revision {revision} for {name}...")
    subprocess.run(["git", "-C", path, "checkout", revision], check=True)

    if sparse_paths:
        for sparse_path in sparse_paths:
            move_files_to_parent(path, sparse_path)


def replace_version_placeholder(manifest_content, version):
    """
    Replace the VERSION_PLACEHOLDER in the manifest content with the actual version.

    Args:
        manifest_content (str): The content of the manifest file.
        version (str): The version to replace the placeholder with.

    Returns:
        str: Updated manifest content.
    """
    return manifest_content.replace("VERSION_PLACEHOLDER", version)


def delete_git_folders(base_path):
    """
    Recursively delete all .git folders in the given directory.

    Args:
        base_path (str): The root directory to search for .git folders.
    """
    for root, dirs, files in os.walk(base_path):
        if ".git" in dirs:
            git_folder = os.path.join(root, ".git")
            print(f"Deleting {git_folder}...")
            
            # Ensure all files are writable
            for dirpath, _, filenames in os.walk(git_folder):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    os.chmod(filepath, 0o777)  # Make file writable
            
            try:
                shutil.rmtree(git_folder)
            except PermissionError as e:
                print(f"PermissionError encountered: {e}")
                # Try removing individual files and retry
                for dirpath, _, filenames in os.walk(git_folder):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            os.remove(filepath)
                        except Exception as inner_e:
                            print(f"Failed to delete {filepath}: {inner_e}")
                shutil.rmtree(git_folder)


def main():
    if not os.path.exists(MANIFEST_FILE):
        print(f"Manifest file {MANIFEST_FILE} not found.")
        return

    # Read the manifest file
    with open(MANIFEST_FILE, "r") as file:
        manifest_content = file.read()

    # Extract the version
    tree = ET.ElementTree(ET.fromstring(manifest_content))
    root = tree.getroot()
    version = root.find("./property[@name='version']").get("value")

    if not version:
        print("Version property not found in the manifest file.")
        return

    # Replace the version placeholder in the manifest content
    manifest_content = replace_version_placeholder(manifest_content, version)

    # Parse the updated manifest
    tree = ET.ElementTree(ET.fromstring(manifest_content))
    root = tree.getroot()

    # Parse remotes
    remotes = {remote.get("name"): remote.get("fetch") for remote in root.findall("remote")}

    # Parse projects and clone them
    for project in root.findall("project"):
        name = project.get("name")
        remote_name = project.get("remote")
        path = project.get("path")
        revision = project.get("revision")

        sparse_paths = [sparse.get("path") for sparse in project.findall("sparse")]

        remote_url = remotes.get(remote_name)
        if not remote_url:
            print(f"Remote {remote_name} for project {name} not found in remotes.")
            continue
        full_url = f"{remote_url}/{name}.git"

        clone_repo(name, full_url, path, revision, sparse_paths)

    # Delete all .git folders
    print("Cleaning up .git folders...")
    for project in root.findall("project"):
        project_path = project.get("path")
        if os.path.exists(project_path):
            delete_git_folders(project_path)


if __name__ == "__main__":
    main()