#!/bin/bash
# 🍎🍎🍎🍎 COMMAND TO PULL CODE
#  ./pull.sh 


echo "🔴 🔴 🔴 🔴 🔴 Tiger Robot GitHub Pull script starting ..."
echo "🔴 🔴 🔴"


# Assign parameters to variables
ssh_key_path=~/.ssh/i_greene
repository_ssh_url=git@github.com:brianmal3/tiger-robot.git

# Echo the parameters for clarity
echo "🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵 Parameters provided:"
echo "🔵 SSH Key Path: $ssh_key_path"
echo "🔵 Repository SSH URL: $repository_ssh_url"
echo 🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵 
# Check if SSH key path file exists
if [ ! -f "$ssh_key_path" ]; then
  echo "👿 SSH key file does not exist at the specified path: $ssh_key_path 👿"
  exit 1
fi

# Check if the repository SSH URL is valid (basic check)
if ! echo "$repository_ssh_url" | grep -q "^git@github.com:.*\.git$"; then
  echo "👿 Repository SSH URL does not seem valid: $repository_ssh_url 👿"
  exit 1
fi

echo
# Set up SSH and check connection
echo "🎽🎽🎽🎽 Pulling the code ... using SSH Key ..."
echo
eval "$(ssh-agent -s)"
ssh-add "$ssh_key_path" || { echo "👿 Failed to add SSH key. 👿"; exit 1; }
ssh -T git@github.com 

# Set the remote URL
echo "🍎 🍎 🍎 Setting remote SSH URL ... $2"
git remote set-url origin "$repository_ssh_url"

echo
# Pull the code
echo "🍎 🍎 🍎 ... Pulling the code ..."
echo
git pull || { echo "👿👿👿👿 Failed to pull code. 👿"; exit 1; }
echo
echo "DONE pulling!! 🥬 🥬 🥬 🥬 🥬 🥬 🥬 🥬 🥬 🥬 🥬"
echo
