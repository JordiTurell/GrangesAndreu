# ADR-006 · `RenderMode` SSR por ruta
**Estado:** aceptado   **Fecha:** 2026-11-11
**Épica:** EP-02 `auth-completo` (contrato: [../auth-completo.md](../auth-completo.md) §6.4 y §6.10)

## Contexto
- `web/src/app/app.routes.server.ts` prerenderiza todo: `{ path: '**', renderMode: RenderMode.Prerender }`. `angular.json` usa `outputMode: "server"` (Express + `AngularNodeAppEngine`); `server.ts` sirve estáticos y delega el resto en el motor, sin log de peticiones.
- La sesión vive en el navegador (ADR-002): el servidor nunca sabe quién es el usuario. Una ruta privada renderizada o prerenderizada en el servidor no tiene datos válidos y arriesga un desajuste de hidratación (`NG0500`).
- `/reset-password?token=…` lleva un secreto de un solo uso en la URL (R-13): Referer, historial, caché y logs del servidor.
- Las pantallas públicas (login, registro, olvidé la contraseña) tienen el mismo HTML para todos.

## Opciones
| Opción | Pros | Contras |
|--------|------|---------|
| A. `Prerender` global (hoy) | Sin cambios | Prerenderiza rutas privadas y la de reseteo; cualquier ruta futura sale prerenderizada |
| B. `Server` para privadas y reseteo | Permite guards en servidor | Sin sesión en servidor el guard solo puede denegar o dejar pasar a ciegas; renderiza la URL con el token |
| C. **Lista explícita de rutas públicas en `Prerender` y todo lo demás `Client`** | Privado por defecto; el token y la sesión nunca pasan por el renderizado; sin hidratación en lo privado | Las rutas privadas no tienen HTML inicial (irrelevante: requieren sesión) |

## Decisión
**Opción C.**
| Ruta | `RenderMode` | Motivo |
|------|--------------|--------|
| `login`, `register`, `forgot-password` | `Prerender` | Formularios idénticos para todos, sin datos ni llamadas a la API al renderizar; mejor primer pintado |
| `reset-password` | `Client` + `headers: { 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store' }` | Token en la query: nunca se renderiza ni se prerenderiza; con `Client` tampoco hay desajuste de hidratación (el estado «sin enlace válido» solo existe en el navegador) |
| `inicio` y cualquier ruta privada futura | `Client` (cubiertas por `**`) | Sesión solo en el navegador |
| `''` y `**` | `Client` | Redirecciones de cliente; fail-safe: una ruta nueva es CSR hasta que se decida otra cosa |

Reglas asociadas:
1. **Guards:** `authGuard` en el servidor **nunca concede** (devuelve `UrlTree('/login')`) y `guestGuard` deja pasar; no llegan a ejecutarse con las rutas privadas en `Client`, pero quedan fail-closed si alguien cambia el modo.
2. **Token de reseteo:** se lee en el navegador (`afterNextRender`), se quita de la URL con `replaceUrl`, no se escribe en consola, almacenamiento ni logs; `<meta name="referrer" content="no-referrer">` global en `index.html` más la cabecera de la ruta. Si `ServerRoute.headers` no se emite en una ruta `Client` (lo comprueba QA con `serve:ssr:web`), middleware de Express en `server.ts` para `/reset-password`.
3. **`server.ts` no registra URLs ni query strings** (no se añade logging de peticiones sin redactar `token`).
4. **Alternativa descartada:** mover el token al fragmento `#token=` (no llega al servidor ni a logs de proxy) exigiría cambiar `build_password_reset_url`; el usuario fijó `?token=` como requisito. Residuo aceptado: la petición inicial llega al servidor del Front y el historial del navegador puede conservarla (caducidad de 30 minutos, un solo uso).
5. **Rutas públicas prerenderizadas:** lo que dependa de la query o del almacenamiento (aviso `motivo`, `returnUrl`) se fija en `afterNextRender`, no en el primer pase.

## Consecuencias
- **Web (WEB-001, WEB-003):** `app.routes.server.ts` con la tabla anterior; `index.html` con el meta `referrer`; posible middleware en `server.ts` (WEB-003).
- **Tests:** FE-RT-* y FE-SSR-* (contrato §7.7): `npm run build` genera `login/`, `register/` y `forgot-password/` prerenderizados y ningún `inicio` ni `reset-password` con contenido; la cabecera `Referrer-Policy` en `/reset-password`; sin `NG0500` en consola.
- **API:** ninguna.

## Tareas derivadas
WEB-001 (rutas y modos), WEB-003 (cabeceras y reset).
