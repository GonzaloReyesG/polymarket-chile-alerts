# main.py
from dotenv import load_dotenv
from data import (
    fetch_event_and_markets,
    build_price_params,
    fetch_prices,
    market_outcomes_and_tokens,
    compute_mid,
)
from mailer import send_email

EVENT_ID = 23947
TOP_N = 15

ALERT_RULES = [
    {"name": "Evelyn Matthei", "type": "price_lt", "threshold": 0.077},
    {"name": "Jeannette Jara", "type": "prob_lt", "threshold": 0.12},
]

def _liq(m):
    try:
        return float(m.get("liquidityNum") or m.get("liquidity") or 0)
    except Exception:
        return 0.0

def _match_rule(market_title: str, outcome_label: str):
    out_lower = (outcome_label or "").lower()
    if out_lower != "yes":
        return []
    title_lower = (market_title or "").lower()
    return [r for r in ALERT_RULES if r["name"].lower() in title_lower]

def main():
    load_dotenv()
    event = fetch_event_and_markets(EVENT_ID)
    markets = event.get("markets") or []

    candidates = [m for m in markets if m.get("active") and _liq(m) > 0]
    candidates.sort(key=_liq, reverse=True)
    top_markets = candidates[:TOP_N]

    price_params = build_price_params(top_markets)
    price_map = fetch_prices(price_params)

    print(f"=== {event.get('title')} — slug: {event.get('slug')} ===\n")
    triggered = []

    for m in top_markets:
        title = m.get("question") or m.get("title") or m.get("slug")
        print(f"[{title}]")
        for outcome_label, token_id in market_outcomes_and_tokens(m):
            by_side = price_map.get(token_id, {})
            try:
                bid = float(by_side.get("BUY") or 0)
                ask = float(by_side.get("SELL") or 0)
            except Exception:
                bid = ask = 0
            mid = compute_mid(bid, ask)
            mid_str = "n/a" if mid is None else f"{mid:.6f}"
            pct_str = "n/a" if mid is None else f"{mid*100:.2f}%"
            print(f"  - {outcome_label:6s} | MID={mid_str} | Prob≈{pct_str}")

            for rule in _match_rule(title, outcome_label):
                if mid is not None and mid < float(rule["threshold"]):
                    triggered.append({
                        "candidate": rule["name"],
                        "mid": mid
                    })
        print()

    # ---- Enviar email si hay alertas ----
    if triggered:
        # Si es una sola alerta → asunto personalizado
        if len(triggered) == 1:
            cand = triggered[0]["candidate"]
            prob = f"{triggered[0]['mid']*100:.2f}%"
            subject = f"{cand} → Probabilidad: {prob}"
        else:
            subject = f"{len(triggered)} Alertas — Chile Presidential Election (Polymarket)"

        # Texto plano
        text_lines = ["CANDIDATO | PROBABILIDAD | PRECIO ACTUAL\n"]
        for a in triggered:
            prob = f"{a['mid']*100:.2f}%"
            price = f"{a['mid']:.4f}"
            text_lines.append(f"{a['candidate']} | {prob} | {price}")
        body_text = "\n".join(text_lines)

        # HTML minimalista tipo CTA
        rows_html = "".join(
            f"""
            <tr>
              <td style="padding:10px 12px; font-weight:600;">{a['candidate']}</td>
              <td style="padding:10px 12px; text-align:right;">{a['mid']*100:.2f}%</td>
              <td style="padding:10px 12px; text-align:right;">{a['mid']:.4f}</td>
            </tr>
            """
            for a in triggered
        )
        body_html = f"""
        <div style="font-family:Inter,Segoe UI,Roboto,Arial,Helvetica,sans-serif;line-height:1.45;color:#111;">
          <h2 style="margin:0 0 12px 0;">🚨 Oportunidad detectada</h2>
          <p style="margin:0 0 14px 0; color:#444;">CTA automático desde Polymarket:</p>

          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; min-width:420px; border:1px solid #eee;">
            <thead>
              <tr style="background:#111; color:#fff;">
                <th align="left"  style="padding:10px 12px;">CANDIDATO</th>
                <th align="right" style="padding:10px 12px;">PROBABILIDAD</th>
                <th align="right" style="padding:10px 12px;">PRECIO ACTUAL</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>

          <p style="margin:14px 0 0 0; color:#666;">📅 Polymarket · Render Job · Script educativo 🚀</p>
        </div>
        """

        send_email(subject, body_text, body_html)
        print(f"\n[✅ EMAIL ENVIADO: {subject}]")
    else:
        print("\n✅ No se disparó ninguna alerta.")

if __name__ == "__main__":
    main()
