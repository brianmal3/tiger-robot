echo "🔷🔷🔷🔷🔷  FNB Recon Robot GitHub Push starting ..."
echo "🔷🔷🔷"

# Ensure the script is called with three arguments
if [ "$#" -ne 1 ]; then
  echo "👿 Please enter required parameter: commit message. 👿"
  exit 1
fi

echo 🔵🔵🔵🔵 Committing ........
git add .
git commit -m "$1"

echo 🔵🔵🔵🔵 Pushing ........
git push

echo 🥬🥬🥬🥬🥬🥬🥬 GitHub push completed!
echo "🔷🔷🔷"
