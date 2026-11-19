# HassDNS Alexa — AGENTS.md

Integración de Home Assistant + skill pública de Amazon Alexa + nube HassDNS.
El usuario entra a su Alexa app, habilita la skill, vincula su Home Assistant
por OAuth, elige entidades desde un panel visual (sin YAML) y las controla por
voz. Reemplaza el flujo nativo de HA (configuración en texto).

## Arquitectura end-to-end

```
Alexa app/Echo → Alexa Skill (Amazon)
  → AWS Lambda proxy (us-east-1 / eu-west-1 / us-west-2)
    → https://alexa.ha-cloud.es/api/alexa.php        (Plesk, ha-cloud.es)
      → HA del usuario: /api/alexa/smart_home        (endpoint nativo HA)
```

- `AcceptGrant` lo gestiona la nube (`supports_auth=False` en el componente).
- La nube guarda tokens HA cifrados AES-256-GCM y tokens OAuth hasheados.
- Eventos proactivos (ChangeReport): HA → `ha-cloud.es/api/proactive_token.php`
  → token LWA → Alexa event gateway.
- OAuth/account linking: `ha-cloud.es/oauth/authorize.php` acepta
  `ha_url` + `ha_token` (LLAT) o el botón "Vincular demo" (usa `demo_ha_url`
  + `demo_ha_token` de `config.php` server-side — nunca expuestos).

## Repos

| Repo | Ruta local | Deploy |
|---|---|---|
| `mavksoft/hassdns-alexa` (este) | `~/Developer/Apps/hassdns-alexa` | HACS custom repo (pendiente catálogo: `hacs/default#14507`) |
| `ha-cloud.es` | `~/Developer/Webs/Git ha-cloud.es` | **manual**: `scp` a `root@dualrdp.com:/var/www/vhosts/ha-cloud.es/httpdocs/public/` (no es git checkout) |
| `hassdns.com` | `~/Developer/Webs/Git hassdns.com` | git pull automático (push basta) |

## IDs y endpoints

- Skill ID: `amzn1.ask.skill.68ca3cbb-a3fc-409a-b131-0877c42bb365`
- Lambdas: `us-east-1`, `eu-west-1`, `us-west-2` (`lambda/deploy.sh`)
- ASK CLI local: `_tools/node/bin/ask` + `_tools/node/lib/node_modules/ask-cli`
- AWS venv: `_tools/aws-venv`
- Cloud: `https://ha-cloud.es` · `https://alexa.ha-cloud.es/api/alexa.php`
- OAuth: `https://ha-cloud.es/oauth/authorize.php`

## Demo de certificación (testers Amazon)

HA en Docker sobre Debian12 (Proxmox VM200), ruta alternativa WAN:8443 —
NO toca la producción `mavksoft.hassdns.com` (misma WAN, 443/8123/22222).

- URL pública: `https://demo.ha-cloud.es:8443` (CNAME→mavksoft.hassdns.com)
- Usuario: `amazon-cert` (password: resetear con
  `docker exec ha-demo hass --script auth -c /config change_password amazon-cert '<nueva>'`
  — requiere reinicio: el proceso cachea credenciales en memoria)
- LLAT 10 años: `/tmp/at.txt` en Debian12 (privado, también referenciado
  server-side en `config.php` del Plesk como `demo_ha_token`)
- Contenedor `ha-demo` (`unless-stopped`), config `/opt/ha-demo/config`
- Apache :8443 → proxy HTTP+WS → HA:8123 (TLS ZeroSSL manual, ~90d)
- Entidades: 4 `input_boolean` demo (lamp/switch/fan/blind) + backup

## SSH

| Máquina | Acceso |
|---|---|
| Debian12 (VM200, 192.168.4.4) | `ssh -i ~/.ssh/devin_ha -J Administrador@mavksoft.hassdns.com:22222 root@192.168.4.4` — **tiene Apache :80 y magic-ia :5010, no tocar** |
| Plesk (ha-cloud.es) | `ssh -i ~/.ssh/devin_dualrdp root@dualrdp.com` |
| Proxmox | `root@192.168.4.5` vía el mismo jump; `qm guest exec 200 -- <cmd>` |

## Verificación (smoke tests)

```bash
# 1. HA demo vivo
curl -sk https://demo.ha-cloud.es:8443/api/config -H "Authorization: Bearer $(ssh -i ~/.ssh/devin_ha -J Administrador@mavksoft.hassdns.com:22222 root@192.168.4.4 'cat /tmp/at.txt')"

# 2. Discover directo al endpoint smart_home
curl -sk https://demo.ha-cloud.es:8443/api/alexa/smart_home -X POST \
  -H "Authorization: Bearer <LLAT>" -H "Content-Type: application/json" \
  -d '{"directive":{"header":{"namespace":"Alexa.Discovery","name":"Discover","payloadVersion":"3","messageId":"t1"},"payload":{}}}'

# 3. Pipeline real (OAuth→link→token→proxy): ejecutar EN EL PLESK
#    (usa hc_links + config.php; no sacar secretos del server)
```

## Reglas duras del proyecto

- `public/.htaccess` lleva `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`
  — sin eso Apache/php-fpm strippea el Bearer y TODO el pipeline da 401
  (fix 7af7ae9 — nunca quitar).
- HA 2026.x **ignora `http:` en YAML** — `use_x_forwarded_for` +
  `trusted_proxies` viven en `.storage/http` (`/opt/ha-demo/config/.storage/`).
- UFW del Debian: `8443/tcp ALLOW` añadido; no tocar reglas existentes.
- ZeroSSL `demo.ha-cloud.es`: renovación MANUAL por DNS-01 cada ~80-90d
  (`acme.sh` en Debian12 + TXT `_acme-challenge.demo` en PowerDNS).
- Nunca tokens/secrets en el repo ni en respuestas al usuario.
- i18n: 6 idiomas (es/en/de/fr/it/pt) en toda cadena nueva — `lib/i18n/`.
- Commit + push inmediato; registrar cada fix en CodeLink (`hassdns-alexa`).

## Pendientes (estado 19-nov-2026)

- ⏳ Amazon certificación: skill enviada, en revisión (ETA en consola ASK).
  Si piden cuenta de pruebas → botón "Vincular demo" de la página OAuth.
- ⏳ HACS catálogo: PR `hacs/default#14507` abierto (brand/ local desde
  HA 2026.3 — el repo brands ya no acepta customs).
- ⏳ Renovar cert ZeroSSL demo ~feb-2027 (manual, DNS-01).
- Rotar el LLAT demo si expira la revisión (está en output histórico de
  sesiones — considerar rotación: `hass --script auth` o long_lived_token API).
- Sidebar del panel sigue `mdi:amazon-alexa` (HA solo admite mdi: ahí;
  el logo propio va en `brand/` y en el header del panel).
