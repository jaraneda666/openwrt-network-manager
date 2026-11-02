#!/bin/sh
# Tool: router_backup.sh
#
# ## Metadata
# - Nombre: router_backup.sh
# - Versión: 2.0
# - Lenguaje: Shell (POSIX / ash)
# - Creada en proyecto: OpenWrt_Manager
# - Fecha de creación: 2026-10-14
# - Descripción: Respaldo automatizado integral de OpenWrt (configuraciones UCI, archivos del sistema, inventario de paquetes de usuario con lista opkg y hook uci-defaults para auto-restauración desatendida) con almacenamiento en Synology NAS (/mnt/nas), verificación de integridad y rotación a 30 días.
# - Parámetros: ninguno
# - Dependencias: sysupgrade, tar, sha256sum, awk
#
# ## Código

LOG_TAG="router_backup"
logger -t "$LOG_TAG" "Iniciando respaldo automatizado de configuracion y paquetes..."

BACKUP_DIR="/mnt/nas"
LOCAL_FALLBACK="/root/backups_local"
TIMESTAMP=$(date +%Y-%m-%d-%H-%M-%S)
BACKUP_NAME="backup-Router_Casa-${TIMESTAMP}.tar.gz"
TEMP_ARCHIVE="/tmp/${BACKUP_NAME}"

# 1. Asegurar punto de montaje de respaldos en NAS
if ! grep -q '/mnt/nas' /proc/mounts; then
  logger -t "$LOG_TAG" "Punto /mnt/nas no montado. Intentando montar..."
  mkdir -p /mnt/nas
  mount -t cifs //192.168.1.100/respaldos /mnt/nas -o user=admin,password=os.environ.get("ADMIN_PASS", ""),vers=2.0,file_mode=0777,dir_mode=0777 >/dev/null 2>&1
fi

TARGET_DIR="$BACKUP_DIR"
if ! grep -q '/mnt/nas' /proc/mounts; then
  logger -t "$LOG_TAG" "[AVISO] NAS no disponible. Usando almacenamiento local: $LOCAL_FALLBACK"
  mkdir -p "$LOCAL_FALLBACK"
  TARGET_DIR="$LOCAL_FALLBACK"
fi

# 2. Capturar inventario de paquetes
mkdir -p /etc/backup
awk '/^Package:/{pkg=$2} /^Status: install user installed/{print pkg}' /usr/lib/opkg/status | sort -u > /etc/backup/user_packages.txt
opkg list-installed > /etc/backup/all_packages.txt

# 3. Asegurar scripts de restauracion dentro de /etc/backup/
cp /usr/bin/restore_packages.sh /etc/backup/restore_packages.sh 2>/dev/null || true
chmod +x /etc/backup/restore_packages.sh 2>/dev/null || true

# Preparar hook de uci-defaults para auto-restauracion al primer booteo tras restore
mkdir -p /etc/uci-defaults
cat << 'EOF' > /etc/uci-defaults/99_auto_restore.sh
#!/bin/sh
if [ -f /etc/backup/restore_packages.sh ]; then
  sh /etc/backup/restore_packages.sh &
fi
exit 0
EOF
chmod +x /etc/uci-defaults/99_auto_restore.sh

# 4. Asegurar que /etc/sysupgrade.conf contenga todos los archivos y rutas requeridas
SYSUP_CONF="/etc/sysupgrade.conf"
for custom_item in \
  "/etc/backup" \
  "/etc/uci-defaults/99_auto_restore.sh" \
  "/sbin/guest_wifi" \
  "/usr/bin/wifi_schedule.sh" \
  "/usr/bin/router_backup.sh" \
  "/usr/bin/restore_packages.sh" \
  "/usr/lib/opennds/theme_casa_invitados_1click.sh" \
  "/etc/adguardhome.yaml"; do
  if [ -e "$custom_item" ]; then
    if ! grep -F -q "$custom_item" "$SYSUP_CONF" 2>/dev/null; then
      echo "$custom_item" >> "$SYSUP_CONF"
    fi
  fi
done

# 5. Generar archivo de respaldo estándar sysupgrade
sysupgrade -b "$TEMP_ARCHIVE" >/dev/null 2>&1
RES=$?

# Remover hook temporal de uci-defaults y la linea de sysupgrade.conf para el sistema activo
rm -f /etc/uci-defaults/99_auto_restore.sh
sed -i '/99_auto_restore.sh/d' "$SYSUP_CONF" 2>/dev/null || true

if [ $RES -ne 0 ] || [ ! -f "$TEMP_ARCHIVE" ]; then
  logger -t "$LOG_TAG" "[ERROR] Falló sysupgrade -b al generar $TEMP_ARCHIVE"
  rm -f "$TEMP_ARCHIVE"
  exit 1
fi

# 6. Mover respaldo a destino y verificar integridad
DEST_FILE="${TARGET_DIR}/${BACKUP_NAME}"
cp "$TEMP_ARCHIVE" "$DEST_FILE"
if tar -tzf "$DEST_FILE" >/dev/null 2>&1; then
  # Generar checksum sha256
  (cd "$TARGET_DIR" && sha256sum "$BACKUP_NAME" > "${BACKUP_NAME}.sha256")
  SIZE=$(ls -lh "$DEST_FILE" | awk '{print $5}')
  logger -t "$LOG_TAG" "[EXITO] Respaldo generado y verificado: $DEST_FILE ($SIZE)"
  echo "OK: $DEST_FILE ($SIZE)"
  rm -f "$TEMP_ARCHIVE"
else
  logger -t "$LOG_TAG" "[ERROR] Archivo en destino corrupto o incompleto."
  rm -f "$TEMP_ARCHIVE"
  exit 1
fi

# 7. Rotacion: mantener respaldos de los ultimos 30 dias
find "$TARGET_DIR" -maxdepth 1 -name "backup-Router_Casa-*.tar.gz" -mtime +30 -exec rm -f {} + 2>/dev/null
find "$TARGET_DIR" -maxdepth 1 -name "backup-Router_Casa-*.tar.gz.sha256" -mtime +30 -exec rm -f {} + 2>/dev/null

exit 0
