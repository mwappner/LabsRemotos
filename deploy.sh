cd ..
rsync -av --exclude='*.git' --exclude='__pycache__' --exclude='deploy.sh' --exclude='.idea' --exclude='data_backup' ./lvdf lvdf@ssh-lvdf.alwaysdata.net:~
cd lvdf
ssh -t lvdf@ssh-lvdf.alwaysdata.net 'cd lvdf; pip uninstall lvdf -y && pip install .'
