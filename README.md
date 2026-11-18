# HassDNS Alexa

Puente Alexa ↔ Home Assistant con panel visual de exposición de entidades,
servido por [ha-cloud.es](https://ha-cloud.es).

Componentes del repositorio:

| Carpeta | Qué es |
|---|---|
| `custom_components/hassdns_alexa` | Integración de Home Assistant (config flow + panel visual + endpoint smart_home) |
| `lambda/` | Función AWS Lambda que proxea directivas Alexa → `ha-cloud.es/api/alexa.php` |
| `skill/` | Manifest de la Alexa Smart Home skill (6 locales, 3 regiones) |

La web cloud vive en otro repo privado: `mavksoft/ha-cloud.es`.

## Instalación en Home Assistant

1. Copia `custom_components/hassdns_alexa` a `<config>/custom_components/hassdns_alexa`
   (o añade el repo como custom repository en HACS).
2. Reinicia Home Assistant.
3. **Ajustes → Dispositivos y servicios → Añadir integración → "HassDNS Alexa"**.
4. Indica la **URL pública HTTPS** de tu Home Assistant (la que Alexa alcanzará:
   tu dominio HassDNS, Nabu Casa remote, DuckDNS…). La integración genera
   automáticamente un token de enlace de larga duración.
5. Aparece un panel **"Alexa"** en la barra lateral: pulsa el icono de enlace
   (arriba a la derecha) para ver URL + token.

## Vinculación con Alexa

1. En la app Alexa: **Skills → HassDNS Alexa → Habilitar**.
2. La app abre la página de `ha-cloud.es`: pega la URL y el token del panel.
3. Alexa redescubre dispositivos → solo llegan las entidades que marcaste
   expuestas en el panel.

## Panel de exposición

En vez de la lista en texto de la configuración nativa, el panel muestra todas
las entidades soportadas **agrupadas por áreas**, con buscador y toggles —
marcas qué expone Alexa y se guarda al instante (no requiere reinicio, el
próximo `Discover` ya lo ve).

## Arquitectura

```
Alexa → Lambda (us-east-1/eu-west-1/us-west-2)
      → ha-cloud.es/api/alexa.php      (resuelve link por bearer OAuth)
      → <tu-ha>/api/alexa/smart_home   (SmartHomeView del core, con el link token)
      → respuesta Alexa

Eventos proactivos: HA → ha-cloud.es/api/proactive_token.php → token LWA
→ ChangeReport a Alexa
```

- `AcceptGrant` lo resuelve la nube (guarda el refresh LWA cifrado) — HA nunca
  lo ve (`supports_auth=False`).
- Los tokens de enlace se guardan **cifrados AES-256-GCM** en la nube.

## Skill ID

`amzn1.ask.skill.68ca3cbb-a3fc-409a-b131-0877c42bb365`

## Operación (deploy, herramientas, demo)

- **ask-cli**: `_tools/node/bin/ask` (node local del repo — no hay node global
  en el Mac; `export PATH=_tools/node/bin:$PATH` primero). Config/perfil LWA
  en `~/.ask/cli_config` (vendor `M22UAR6Q59533X`, aws_profile
  `hassdns-alexa`).
- **Lambdas**: `hassdns-alexa-proxy` en us-east-1 / eu-west-1 / us-west-2,
  trigger `alexa-connectedhome.amazon.com` ligado al skill ID. Deploy:
  `lambda/deploy.sh`.
- **Cloud** (`ha-cloud.es` en Plesk): deploy manual por `scp` — httpdocs NO
  es git checkout. Config secreta fuera de git en
  `httpdocs/config/config.php` (LWA + demo_ha_* + crypt_key).
  OJO: `.htaccess` lleva `SetEnvIf Authorization` — sin él PHP-FPM no ve el
  Bearer (bug 18-nov-2026).
- **Skill en certificación**: el manifest queda bloqueado mientras dure la
  revisión (403 a PUT manifest). `testingInstructions` va a nivel
  `publishingInformation` (no por locale). La página OAuth tiene botón
  "Vincular demo" para testers (creds server-side, `config.demo_ha_*`).
- **HA demo** `demo.ha-cloud.es:8443`: Docker `ha-demo` en Debian12 Proxmox
  VM200 (`192.168.4.4`); Apache vhost :8443 con LE → proxy a :8123; forward
  router WAN 8443→192.168.4.4:8443; ufw allow 8443. Detalles: AGENTS.md
  global + fix_logs #3069/#3070 de CodeLink.
- CodeLink proyecto: `hassdns-alexa`.
