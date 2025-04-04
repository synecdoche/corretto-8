import io
import os
import os.path
import shlex
import string
import subprocess
import sys

# File in the OpenJDK8 repo containing current version numbers.
OPENJDK8_VERSION_FILE = 'common/autoconf/version-numbers'
MAJOR_VERSION = '8'
POINT_VERSION = '1'
VERSION_TXT = 'version.txt'
GIT_NAME = 'corretto-github-robot'
GIT_EMAIL = 'no-reply@amazon.com'

def initialize_git(name: str, email: str, branch: str):
    cmd = f'git config user.name {name}'
    cmdline = shlex.split(cmd)
    output = subprocess.check_output(cmdline)
    cmd = f'git config user.email {email}'
    cmdline = shlex.split(cmd)
    output = subprocess.check_output(cmdline)
    cmd = f'git checkout {branch}'
    cmdline = shlex.split(cmd)
    output = subprocess.check_output(cmdline)

def parse_openjdk8_version_file(version_file: str) -> dict:
    # parse out lines with key/value pairs split by an equals sign.
    d = {}
    variable_start_characters = set(string.ascii_letters)
    with open(version_file) as f:
        for line in f:
            if line[0] in variable_start_characters:
                try:
                    key, value = line.strip().split('=')
                except ValueError:
                    # not a valid line. no worries.
                    pass
                d[key] = value
    return d


# 8.462.00.1
def parse_version_txt(version_txt_file_path: str) -> tuple:
    '''Return a 4-tuple containing:
    MAJOR.MINOR.BUILD.POINT
    '''
    with open(version_txt_file_path) as f:
        version_str = f.read()
    return tuple(version_str.strip().split('.'))

def list_git_tags_matching_version(ver: str, upstream_remote: str) -> list[str]:
    # jdk8u452
    list_git_tags_cmd = f'git ls-remote --tags {upstream_remote}'
    cmdline = shlex.split(list_git_tags_cmd)
    tags = []
    git_proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
    for line in io.TextIOWrapper(git_proc.stdout, encoding='utf-8'):
        index = line.find(ver)
        if index > -1:
            tag = line.strip()[index:]
            if not tag.endswith('^{}') and not tag.endswith('-ga'):
                tags.append(tag)
    return sorted(tags)

def format_version_string(major_version: str, update_version: str, build_version: str, point_version: str) -> str:
    '''Given the four components of our version, format them into a string.
    '''
    return f'{major_version}.{update_version}.{build_version}.{point_version}'

def update_version_file(filename: str, version_string: str):
    '''Write out the new version.txt file with the provided version string.
    '''
    with open(filename, 'w') as f:
        f.write(f'{version_string}\n')

def commit_version_txt(filename: str, new_version: str):
    git_commit_cmd = f'git commit -m "Update Corretto version to match upstream: {new_version}" {filename}'
    cmdline = shlex.split(git_commit_cmd)
    output = subprocess.check_output(cmdline)
    return output


def update_version_txt_if_needed(upstream_remote: str, git_branch: str):
    '''Determine the current version, and update the version string in
    'version.txt' as needed.

    Our version.txt file contains a version string with four parts, separated by dots:
      * major version
      * update version
      * build version
      * point version

    The sources of truth of these parts are, respectively:
      * the repository we're in (e.g. Java 8)
      * the version-numbers file checked into the repository
      * git tags
      * version.txt itself

    The point version is reset to 1 if any of the other parts change.
    '''

    initialize_git(GIT_NAME, GIT_EMAIL, git_branch)
    
    cwd = os.getcwd()
    # Read JDK_UPDATE_VERSION from OpenJDK source so we can filter JDK tags to match it.
    file_path = os.path.join(cwd, OPENJDK8_VERSION_FILE)
    version_dict = parse_openjdk8_version_file(file_path)
    file_jdk_update_version = version_dict['JDK_UPDATE_VERSION']
    for k, v in version_dict.items():
        print(f'{k} -> {v}')
        
    version_txt_tuple = parse_version_txt(VERSION_TXT)
    version_txt_update_version, version_txt_build_version = version_txt_tuple[1:3]
    print(f'version tuple: {version_txt_tuple}')

    # get all tags matching the version number from source
    tags = list_git_tags_matching_version(f'jdk{MAJOR_VERSION}u{file_jdk_update_version}', 'openjdk-upstream-u')
    for tag in tags:
        print(f'git tag: {tag}')

    # split out the build version from the git tag, e.g. jdk8u452-b07 -> 07
    newest_tag_build_version = tags[-1].split('-')[1][1:]

    # If minor and build version don't match version_txt, rewrite it.
    # The source of truth is 
    if version_txt_update_version != file_jdk_update_version or \
       version_txt_build_version != newest_tag_build_version:
        new_version_string = format_version_string(MAJOR_VERSION, file_jdk_update_version, newest_tag_build_version, POINT_VERSION)
        print(f'Updating version string from {".".join(version_txt_tuple)} to {new_version_string}')
        update_version_file(VERSION_TXT, new_version_string)
        commit_version_txt(VERSION_TXT, new_version_string)
    else:
        print(f'Corretto version is current.')
        

if __name__ == '__main__':
    upstream_remote = 'upstream' # f'upstream-{sys.argv[1]}'
    branch = 'update_version'
    update_version_txt_if_needed(upstream_remote, branch)
