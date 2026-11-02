#!/bin/sh
# Tool: restore_packages.sh
#
# ## Metadata
# - Nombre: restore_packages.sh
# - Versión: 2.0
# - Lenguaje: Shell (POSIX / ash)
# - Creada en proyecto: OpenWrt_Manager
# - Fecha de creación: 2026-10-14
# - Descripción: Restauración automatizada desatendida de paquetes de usuario y servicios en OpenWrt con verificación de conectividad WAN, actualización de repositorios opkg, re-instalación selectiva de paquetes de usuario y recarga de servicios.
# - Parámetros: ninguno
# - Dependencias: opkg, ping
#
# ## Código

LOG="/var/log/auto_restore.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

log "Iniciando proceso de restauracion automatica..."

# 1. Esperar conectividad WAN (max 90 segundos)
log "Verificando enlace WAN..."
TRIES=0
while [ $TRIES -lt 30 ]; do
  if ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
    log "Conectividad a Internet verificada."
    break
  fi
  sleep 3
  TRIES=$((TRIES + 1))
done

if [ $TRIES -eq 30 ]; then
  log "[ADVERTENCIA] Sin respuesta ICMP WAN tras 90s. Procediendo con intento de instalacion..."
fi

# 2. Actualizar repositorios opkg
log "Actualizando indices opkg..."
opkg update >> "$LOG" 2>&1

# 3. Instalar paquetes de usuario
PKG_FILE="/etc/backup/user_packages.txt"
if [ -f "$PKG_FILE" ]; then
  log "Instalando paquetes de usuario listados en $PKG_FILE..."
  while read -r pkg; do
    [ -z "$pkg" ] && continue
    case "$pkg" in \#*) continue ;; esac
    if ! opkg list-installed | grep -q "^$pkg "; then
      log "Instalando: $pkg..."
      opkg install "$pkg" >> "$LOG" 2>&1
    else
      log "Paquete ya presente: $pkg"
    fi
  done < "$PKG_FILE"
else
  log "[AVISO] No se encontro $PKG_FILE"
fi

# 4. Asegurar permisos de scripts
[ -f /usr/bin/wifi_schedule.sh ] && chmod +x /usr/bin/wifi_schedule.sh
[ -f /sbin/guest_wifi ] && chmod +x /sbin/guest_wifi
[ -f /usr/bin/router_backup.sh ] && chmod +x /usr/bin/router_backup.sh
[ -f /usr/lib/opennds/theme_casa_invitados_1click.sh ] && chmod +x /usr/lib/opennds/theme_casa_invitados_1click.sh
[ -f /etc/rc.local ] && chmod +x /etc/rc.local

# 5. Reiniciar / recargar servicios clave
log "Reiniciando servicios del sistema..."
[ -f /etc/init.d/adguardhome ] && /etc/init.d/adguardhome restart >/dev/null 2>&1
[ -f /etc/init.d/opennds ] && /etc/init.d/opennds restart >/dev/null 2>&1
[ -f /etc/init.d/cron ] && /etc/init.d/cron restart >/dev/null 2>&1
/etc/init.d/firewall reload >/dev/null 2>&1

log "Restauracion automatica finalizada con exito."
exit 0
