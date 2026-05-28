#!/bin/bash
# MonkeyKing daily backup
BACKUP_DIR=/opt/monkeyking/backups
DATA_DIR=/var/lib/docker/volumes/monkeyking_mk_data/_data
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

cp $DATA_DIR/monkeyking.db $BACKUP_DIR/monkeyking_$DATE.db
cp -r $DATA_DIR/uploads $BACKUP_DIR/uploads_$DATE 2>/dev/null
cp -r $DATA_DIR/tailored_cvs $BACKUP_DIR/tailored_cvs_$DATE 2>/dev/null

# Keep only last 7 days of backups
find $BACKUP_DIR -name 'monkeyking_*.db' -mtime +7 -delete
find $BACKUP_DIR -name 'uploads_*' -type d -mtime +7 -exec rm -rf {} + 2>/dev/null
find $BACKUP_DIR -name 'tailored_cvs_*' -type d -mtime +7 -exec rm -rf {} + 2>/dev/null

echo "[$(date)] Backup completed: monkeyking_$DATE.db"
