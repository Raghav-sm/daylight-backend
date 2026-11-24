from __future__ import annotations

import html
from urllib.parse import urlparse


_DAYLIGHT_WORDMARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 10 208 62" fill="none" role="img" aria-label="Daylight" class="wordmark">
  <rect x="0" y="12" width="9.05" height="46" fill="var(--foreground)" />
  <path d="M 9.05 12 A 23 23 0 0 1 9.05 58 L 9.05 12 Z" fill="var(--amber)" />
  <g fill="var(--foreground)" stroke="var(--foreground)" stroke-width="24" stroke-linejoin="round" paint-order="stroke fill">
    <path transform="translate(32.630 58.000) scale(0.028320313 -0.028320313)" d="M471 -26Q365 -26 278.5 14Q192 54 141 131Q90 208 90 318Q90 414 128 474Q166 534 229.5 568.5Q293 603 370 620Q447 637 525 647Q625 660 688 667Q751 674 781.5 691Q812 708 812 749L812 755Q812 825 786 873.5Q760 922 708 948Q656 974 578 974Q498 974 441 949Q384 924 348.5 886.5Q313 849 295 810L122 867Q165 969 238 1026.5Q311 1084 399 1108Q487 1132 573 1132Q629 1132 700.5 1118.5Q772 1105 838.5 1065Q905 1025 948.5 946.5Q992 868 992 737L992 0L815 0L815 152L803 152Q784 113 742 71.5Q700 30 633 2Q566 -26 471 -26ZM502 133Q602 133 671 172Q740 211 776 273.5Q812 336 812 404L812 559Q801 546 764 535.5Q727 525 679.5 517Q632 509 587.5 503.5Q543 498 517 495Q452 487 395.5 467.5Q339 448 305 410.5Q271 373 271 309Q271 251 301 212Q331 173 383 153Q435 133 502 133Z" />
    <path transform="translate(63.363 58.000) scale(0.028320313 -0.028320313)" d="M140 -405L186 -249L205 -254Q260 -268 305 -261.5Q350 -255 386 -217Q422 -179 449 -99L481 -6L54 1118L251 1118L489 455Q527 351 553 249Q579 147 608 51L542 51Q571 147 597.5 249.5Q624 352 661 455L901 1118L1097 1118L606 -167Q572 -256 524.5 -313.5Q477 -371 414 -398.5Q351 -426 272 -426Q224 -426 189 -419Q154 -412 140 -405Z" />
    <path transform="translate(95.257 58.000) scale(0.028320313 -0.028320313)" d="M338 1490L338 0L158 0L158 1490Z" />
    <path transform="translate(108.318 58.000) scale(0.028320313 -0.028320313)" d="M158 0L158 1118L338 1118L338 0ZM249 1301Q198 1301 161 1336Q124 1371 124 1420Q124 1470 161 1504.5Q198 1539 249 1539Q301 1539 338 1504.5Q375 1470 375 1420Q375 1371 338 1336Q301 1301 249 1301Z" />
    <path transform="translate(121.378 58.000) scale(0.028320313 -0.028320313)" d="M611 -442Q487 -442 396.5 -410.5Q306 -379 246 -327Q186 -275 151 -214L297 -120Q321 -152 356.5 -191Q392 -230 452.5 -257.5Q513 -285 611 -285Q745 -285 831.5 -221Q918 -157 918 -19L918 205L901 205Q882 173 847.5 129Q813 85 748.5 51.5Q684 18 576 18Q442 18 335 81.5Q228 145 166 267Q104 389 104 564Q104 737 165 864.5Q226 992 333.5 1062Q441 1132 580 1132Q688 1132 752.5 1096.5Q817 1061 852 1015Q887 969 906 939L923 939L923 1118L1098 1118L1098 -29Q1098 -173 1033 -264.5Q968 -356 857.5 -399Q747 -442 611 -442ZM606 178Q708 178 778 224.5Q848 271 884 358.5Q920 446 920 568Q920 687 884.5 777.5Q849 868 779 919.5Q709 971 606 971Q500 971 429 916.5Q358 862 322.5 771Q287 680 287 568Q287 453 323 365Q359 277 430 227.5Q501 178 606 178Z" />
    <path transform="translate(155.963 58.000) scale(0.028320313 -0.028320313)" d="M338 670L338 0L158 0L158 1490L338 1490L338 847L307 847Q358 1002 452.5 1067Q547 1132 674 1132Q787 1132 872.5 1085.5Q958 1039 1005.5 945.5Q1053 852 1053 710L1053 0L872 0L872 695Q872 824 804.5 897Q737 970 620 970Q540 970 476 935Q412 900 375 833Q338 766 338 670Z" />
    <path transform="translate(189.273 58.000) scale(0.028320313 -0.028320313)" d="M598 1118L598 964L20 964L20 1118ZM188 1384L368 1384L368 290Q368 215 398.5 180.5Q429 146 500 146Q517 146 543.5 150Q570 154 592 158L629 6Q601 -4 565.5 -9Q530 -14 495 -14Q350 -14 269 62.5Q188 139 188 276Z" />
  </g>
</svg>"""

_DAYLIGHT_MARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 46 46" fill="none" aria-hidden="true" width="22" height="22">
  <rect x="6.975" y="0" width="9.05" height="46" fill="var(--foreground)" />
  <path d="M 16.025 0 A 23 23 0 0 1 16.025 46 L 16.025 0 Z" fill="var(--amber)" />
</svg>"""

_READ_ICON_SVG = """<svg viewBox="0 0 20 20" fill="none" aria-hidden="true" width="16" height="16">
  <path d="M2.5 10s2.8-5 7.5-5 7.5 5 7.5 5-2.8 5-7.5 5-7.5-5-7.5-5Z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="10" cy="10" r="2.25" stroke="currentColor" stroke-width="1.6"/>
</svg>"""

_WRITE_ICON_SVG = """<svg viewBox="0 0 20 20" fill="none" aria-hidden="true" width="16" height="16">
  <path d="M4.5 15.5h3.1l7.9-7.9a1.6 1.6 0 0 0 0-2.26l-.84-.84a1.6 1.6 0 0 0-2.26 0L4.5 12.4v3.1Z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M11.2 5.7 14.3 8.8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
</svg>"""

_SHIELD_ICON_SVG = """<svg viewBox="0 0 20 20" fill="none" aria-hidden="true" width="14" height="14">
  <path d="M10 2.5 16 5v4.6c0 3.7-2.55 6.8-6 7.9-3.45-1.1-6-4.2-6-7.9V5l6-2.5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="m7.5 10.1 1.7 1.7 3.4-3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

_LINK_ARROWS_SVG = """<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" width="16" height="16">
  <path d="M7 9h10m0 0-3-3m3 3-3 3M17 15H7m0 0 3 3m-3-3 3-3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def _scope_items(scopes: list[str]) -> str:
    items: list[str] = []
    if "daylight:read" in scopes:
        items.append(
            f"""<li class="perm-item">
              <span class="perm-icon perm-icon-read">{_READ_ICON_SVG}</span>
              <div class="perm-copy">
                <div class="perm-title">Read projects and tasks</div>
                <div class="perm-desc">View your project list, workflow stages, and task details.</div>
              </div>
              <span class="scope-tag">read</span>
            </li>"""
        )
    if "daylight:write" in scopes:
        items.append(
            f"""<li class="perm-item">
              <span class="perm-icon perm-icon-write">{_WRITE_ICON_SVG}</span>
              <div class="perm-copy">
                <div class="perm-title">Create and move tasks</div>
                <div class="perm-desc">Add new tasks to your projects and move them across stages.</div>
              </div>
              <span class="scope-tag">write</span>
            </li>"""
        )
    return "\n".join(items)


def render_consent_page(
    *,
    client_name: str,
    client_id: str,
    redirect_uri: str,
    user_name: str,
    user_email: str,
    scopes: list[str],
    request_handle: str,
    csrf_token: str,
) -> str:
    safe_client = html.escape(client_name)
    safe_client_initial = html.escape((client_name.strip()[:1] or "C").upper())
    client_host = html.escape(urlparse(client_id).netloc or client_id)
    redirect_host = html.escape(urlparse(redirect_uri).netloc or redirect_uri)
    safe_user_name = html.escape(user_name or user_email)
    safe_user_email = html.escape(user_email)
    user_initial = html.escape(((user_name or user_email).strip()[:1] or "U").upper())
    safe_handle = html.escape(request_handle, quote=True)
    safe_csrf = html.escape(csrf_token, quote=True)
    permissions_html = _scope_items(scopes)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Connect {safe_client} to Daylight</title>
  <link rel="icon" href="/icon.svg" type="image/svg+xml" />
  <link rel="icon" href="/favicon.ico" sizes="any" />
  <style>
    :root {{
      color-scheme: light dark;
      --background: #FAF6EE;
      --foreground: #2B2B2B;
      --card: #FFFDF8;
      --secondary: #F1EADB;
      --muted-foreground: #6B6558;
      --border: #E2D9C3;
      --primary: #2B2B2B;
      --primary-foreground: #FAF6EE;
      --amber: #E9A23B;
      --sage: #7FA37A;
      --shadow: 0 24px 60px -24px rgba(43, 43, 43, 0.2), 0 4px 16px -4px rgba(43, 43, 43, 0.08);
      --glow: rgba(233, 162, 59, 0.16);
      --surface-soft: rgba(241, 234, 219, 0.58);
      --amber-soft: rgba(233, 162, 59, 0.14);
      --sage-soft: rgba(127, 163, 122, 0.16);
    }}

    @media (prefers-color-scheme: dark) {{
      :root {{
        --background: #252322;
        --foreground: #F3ECDD;
        --card: #332F2D;
        --secondary: #2B2826;
        --muted-foreground: #B5AAA0;
        --border: #4B4541;
        --primary: #F3ECDD;
        --primary-foreground: #252322;
        --amber: #F0B04F;
        --sage: #8FB78A;
        --shadow: 0 28px 70px -24px rgba(0, 0, 0, 0.62), 0 8px 24px -8px rgba(0, 0, 0, 0.4);
        --glow: rgba(240, 176, 79, 0.14);
        --surface-soft: rgba(37, 35, 34, 0.65);
        --amber-soft: rgba(240, 176, 79, 0.15);
        --sage-soft: rgba(143, 183, 138, 0.16);
      }}
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    html, body {{
      min-height: 100%;
    }}

    body {{
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: var(--background);
      background-image:
        radial-gradient(640px 360px at 50% -60px, var(--glow), transparent 70%),
        radial-gradient(480px 320px at 85% 100%, rgba(127, 163, 122, 0.08), transparent 70%);
      color: var(--foreground);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
      -webkit-font-smoothing: antialiased;
      line-height: 1.5;
    }}

    @keyframes cardIn {{
      from {{
        opacity: 0;
        transform: translateY(10px) scale(0.99);
      }}
      to {{
        opacity: 1;
        transform: translateY(0) scale(1);
      }}
    }}

    .shell {{
      width: 100%;
      max-width: 440px;
      animation: cardIn 260ms cubic-bezier(0.22, 1, 0.36, 1) both;
    }}

    .brand-bar {{
      display: flex;
      justify-content: center;
      margin-bottom: 20px;
    }}

    .wordmark {{
      height: 28px;
      width: auto;
      display: block;
    }}

    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .card-top {{
      padding: 26px 26px 20px;
      text-align: center;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, var(--amber-soft) 0%, transparent 72%);
    }}

    .bridge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-bottom: 18px;
    }}

    .app-tile {{
      width: 48px;
      height: 48px;
      border-radius: 13px;
      background: var(--card);
      border: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      font-weight: 600;
      color: var(--foreground);
      box-shadow: 0 4px 12px -6px rgba(0, 0, 0, 0.25);
    }}

    .app-tile-client {{
      background: linear-gradient(135deg, var(--amber-soft), var(--card));
      border-color: color-mix(in srgb, var(--amber) 40%, var(--border));
      color: var(--amber);
    }}

    .bridge-mid {{
      width: 32px;
      height: 32px;
      border-radius: 999px;
      background: var(--secondary);
      border: 1px solid var(--border);
      color: var(--muted-foreground);
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    h1 {{
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
      margin-bottom: 6px;
    }}

    .subtitle {{
      font-size: 13.5px;
      color: var(--muted-foreground);
    }}

    .host-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 12px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 500;
      color: var(--muted-foreground);
      background: var(--surface-soft);
      border: 1px solid var(--border);
    }}

    .host-dot {{
      width: 6px;
      height: 6px;
      border-radius: 999px;
      background: var(--sage);
    }}

    .card-body {{
      padding: 20px 26px 24px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}

    .account-box {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 12px;
      background: var(--surface-soft);
      border: 1px solid var(--border);
    }}

    .avatar {{
      width: 36px;
      height: 36px;
      border-radius: 999px;
      background: var(--amber-soft);
      border: 1px solid color-mix(in srgb, var(--amber) 35%, var(--border));
      color: var(--amber);
      font-weight: 600;
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}

    .account-meta {{
      min-width: 0;
      flex: 1;
    }}

    .account-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted-foreground);
      font-weight: 600;
    }}

    .account-name {{
      font-size: 13.5px;
      font-weight: 500;
      color: var(--foreground);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .account-email {{
      font-size: 12.5px;
      color: var(--muted-foreground);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .section-label {{
      font-size: 11.5px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted-foreground);
      margin-bottom: 10px;
    }}

    .perm-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .perm-item {{
      display: flex;
      align-items: flex-start;
      gap: 11px;
      padding: 11px 12px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: var(--card);
    }}

    .perm-icon {{
      width: 32px;
      height: 32px;
      border-radius: 9px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 1px;
    }}

    .perm-icon-read {{
      background: var(--sage-soft);
      color: var(--sage);
    }}

    .perm-icon-write {{
      background: var(--amber-soft);
      color: var(--amber);
    }}

    .perm-copy {{
      flex: 1;
      min-width: 0;
    }}

    .perm-title {{
      font-size: 13.5px;
      font-weight: 500;
      color: var(--foreground);
    }}

    .perm-desc {{
      font-size: 12.5px;
      color: var(--muted-foreground);
      margin-top: 2px;
      line-height: 1.4;
    }}

    .scope-tag {{
      font-size: 11px;
      font-weight: 500;
      color: var(--muted-foreground);
      background: var(--secondary);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 8px;
      flex-shrink: 0;
      margin-top: 2px;
    }}

    .reassurance {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      font-size: 12px;
      color: var(--muted-foreground);
      line-height: 1.45;
      padding: 0 2px;
    }}

    .reassurance svg {{
      flex-shrink: 0;
      margin-top: 2px;
      color: var(--sage);
    }}

    .actions {{
      display: grid;
      grid-template-columns: 1fr 1.4fr;
      gap: 10px;
      margin-top: 2px;
    }}

    button {{
      appearance: none;
      font: inherit;
      font-size: 14px;
      font-weight: 500;
      height: 42px;
      border-radius: 10px;
      cursor: pointer;
      transition: transform 120ms ease, opacity 120ms ease, background-color 140ms ease, border-color 140ms ease;
    }}

    button:active {{
      transform: translateY(1px);
    }}

    button:focus-visible {{
      outline: 2px solid var(--amber);
      outline-offset: 2px;
    }}

    .btn-deny {{
      background: var(--secondary);
      color: var(--foreground);
      border: 1px solid var(--border);
    }}

    .btn-deny:hover {{
      border-color: var(--muted-foreground);
    }}

    .btn-approve {{
      background: var(--primary);
      color: var(--primary-foreground);
      border: 1px solid transparent;
      box-shadow: 0 6px 18px -8px rgba(0, 0, 0, 0.38);
    }}

    .btn-approve:hover {{
      opacity: 0.92;
    }}

    .footer {{
      margin-top: 16px;
      text-align: center;
      font-size: 12px;
      color: var(--muted-foreground);
    }}

    .footer strong {{
      font-weight: 500;
      color: var(--foreground);
    }}

    @media (max-width: 420px) {{
      .card-top {{ padding: 22px 18px 18px; }}
      .card-body {{ padding: 18px; }}
      .actions {{ grid-template-columns: 1fr; }}
      .btn-approve {{ order: -1; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <div class="brand-bar">{_DAYLIGHT_WORDMARK_SVG}</div>

    <main class="card">
      <div class="card-top">
        <div class="bridge" aria-hidden="true">
          <div class="app-tile app-tile-client">{safe_client_initial}</div>
          <div class="bridge-mid">{_LINK_ARROWS_SVG}</div>
          <div class="app-tile">{_DAYLIGHT_MARK_SVG}</div>
        </div>
        <h1>Connect {safe_client} to Daylight?</h1>
        <p class="subtitle">{safe_client} is requesting access to your workspace.</p>
        <div class="host-pill">
          <span class="host-dot" aria-hidden="true"></span>
          <span>Verified client · {client_host}</span>
        </div>
      </div>

      <div class="card-body">
        <div class="account-box">
          <div class="avatar" aria-hidden="true">{user_initial}</div>
          <div class="account-meta">
            <div class="account-label">Signed in as</div>
            <div class="account-name">{safe_user_name}</div>
            <div class="account-email">{safe_user_email}</div>
          </div>
        </div>

        <div>
          <div class="section-label">Permissions requested</div>
          <ul class="perm-list">
            {permissions_html}
          </ul>
        </div>

        <p class="reassurance">
          {_SHIELD_ICON_SVG}
          <span>Only your own Daylight data is accessible. You can revoke {safe_client}'s access anytime from Account settings.</span>
        </p>

        <form method="post" action="/oauth/authorize/decision" class="actions">
          <input type="hidden" name="request" value="{safe_handle}" />
          <input type="hidden" name="csrf" value="{safe_csrf}" />
          <button type="submit" name="decision" value="deny" class="btn-deny">Cancel</button>
          <button type="submit" name="decision" value="approve" class="btn-approve">Approve access</button>
        </form>
      </div>
    </main>

    <p class="footer">Approving will return you to <strong>{redirect_host}</strong></p>
  </div>
</body>
</html>"""
