# OpenWrt Network Infrastructure Manager

Herramientas de automatización en Python y PowerShell para administración, respaldo, segmentación de redes VLAN y hardening de enrutadores y puntos de acceso OpenWrt.

---

## Arquitectura y Componentes

- **Gestión:** Protocolo UCI (`uci export/set/commit`) a través de conexiones SSH seguras.
- **Políticas de red:** Configuración de colas SQM CAKE, control de flujo y roaming Wi-Fi 802.11r.
- **Copias de seguridad:** Generación y validación de archivos de respaldo `.tar.gz` de `/etc/config`.

---

## Instrucciones de Uso

```bash
# Auditoría de estado y configuración de red
python tools/openwrt_client.py --host 192.168.1.1 --action audit
```

---

## Consideraciones de Seguridad

- Este repositorio almacena código fuente, utilitarios de prueba y documentación técnica de ingeniería.
- Todas las credenciales, llaves privadas y variables de entorno deben suministrarse de forma local mediante archivos no versionados.
- Las herramientas de auditoría contenidas deben utilizarse exclusivamente en entornos autorizados y laboratorios de prueba.

---

**Autor:** Juan Carlos Araneda M.  
**Licencia:** MIT License (consulte [LICENSE](LICENSE))
