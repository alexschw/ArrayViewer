last_aview_version=$(pip index versions ArrayViewer | grep versions | grep "[0-9][\.0-9]\+" -o | head -1)
current_aview_version=$(head ArrayViewer/__init__.py | grep "[\.0-9]\+" -o)
tag_aview_version=$(git tag -l --contains HEAD | tail -1)
if [[ "$last_aview_version" == "$current_aview_version" ]]; then
    echo "Version is already uploaded. Change __init__.py to match the current version."
    exit
fi
if [[ "$tag_aview_version" != "v$current_aview_version" ]]; then
    echo "Tag does not match the current version. Use 'git tag v$current_aview_version' to do that now."
fi
echo "No match"
python setup.py sdist
echo "Do you wish to upload version $current_aview_version to pypi?"
while true; do
    read -p "(Y)es / (N)o: " yn
    case $yn in
        [Yy]* ) echo "Uploading"; twine upload dist/arrayviewer-$current_aview_version.tar.gz; break;;
        [Nn]* ) echo "Okay. We are not uploading yet"; exit;;
    esac
done

