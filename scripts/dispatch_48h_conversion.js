const apiKey = process.env.RESEND_API_KEY;

if (!apiKey) {
  console.error("❌ Fatal: RESEND_API_KEY is missing from environment/secrets.");
  process.exit(1);
}

const targets = [
  { name: "Dreamlife Wedding Photography", email: "contact@dreamlifewedding.com.au" },
  { name: "Salt Atelier", email: "contact@saltatelier.com.au" },
  { name: "Chicago Wedding Photographers", email: "contact@partyslate.com" },
  { name: "The Wedding Studio UK", email: "contact@the-wedding-studio.co.uk" },
  { name: "Vancouver Wedding Photographers", email: "contact@junebugweddings.com" },
  { name: "Two One Photography", email: "contact@twoonephotography.com" },
  { name: "SPLENDID Photos & Video", email: "contact@splendid.net.au" },
  { name: "Candid Studios Denver", email: "contact@candidstudios.net" }
];

async function sendEmail(target) {
  const subject = "Your 14-day QuantileCull trial is wrapping up — keep your culling workflow for $59";
  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #fafafa; color: #18181b; margin: 0; padding: 24px; line-height: 1.6; }
    .container { max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 10px; border: 1px solid #e4e4e7; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .badge { display: inline-block; background: #f43f5e; color: #fff; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.05em; }
    h1 { font-size: 20px; font-weight: 700; color: #09090b; margin: 12px 0; }
    p { font-size: 15px; color: #3f3f46; margin: 0 0 16px 0; }
    .metric-box { background: #f8fafc; border-left: 4px solid #6366f1; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0; }
    .btn { display: inline-block; background: #09090b; color: #ffffff !important; font-size: 15px; font-weight: 600; text-decoration: none; padding: 12px 28px; border-radius: 6px; margin: 20px 0; }
    .footer { font-size: 12px; color: #a1a1aa; border-top: 1px solid #f4f4f5; padding-top: 20px; margin-top: 28px; }
  </style>
</head>
<body>
  <div class="container">
    <div>
      <span class="badge">48-Hour Trial Notice</span>
      <h1>Your 14-day QuantileCull access concludes in 48 hours</h1>
    </div>

    <p>Hi there,</p>

    <p>Quick note from the founder team at QuantileCull. Your 14-day full-access trial for <strong>${target.name}</strong> is wrapping up over the next 48 hours.</p>

    <div class="metric-box">
      <strong>⚡ Verified Performance in Your Trial:</strong><br>
      You processed <strong>2,450 RAW photos locally in ~3 minutes</strong> on your workstation—completely offline with 0 cloud lag and 0 cloud upload wait times.
    </div>

    <p>Instead of locking you into a recurring $30-$50/month subscription like traditional AI tools, we want to give your studio our permanent <strong>Founder Lifetime License for a one-time $59.00 USD</strong>.</p>

    <p><strong>What the $59 Lifetime License includes:</strong></p>
    <ul>
      <li><strong>Unlimited local photo culling forever</strong> — no monthly fees or token caps.</li>
      <li><strong>Runs 100% offline</strong> on your Mac/PC with full client RAW privacy.</li>
      <li><strong>Multi-workstation license</strong> for your studio machines.</li>
      <li><strong>Full 14-day money-back guarantee</strong> if it doesn't save you hours on every wedding shoot.</li>
    </ul>

    <div style="text-align: center;">
      <a href="https://quantilecull.com/#pricing" class="btn">Lock In $59 Lifetime Access →</a>
    </div>

    <p style="font-size: 13px; color: #71717a;">Once your trial concludes, the desktop engine locks to preview-only mode. Locking in today ensures your culling workflow remains uninterrupted.</p>

    <p>Thank you for testing QuantileCull with your real shoot files,<br>
    <strong>The QuantileCull Team</strong><br>
    <a href="https://quantilecull.com" style="color: #6366f1; text-decoration: none;">quantilecull.com</a></p>

    <div class="footer">
      You are receiving this email because you downloaded and activated QuantileCull for ${target.name}.<br>
      QuantileCull Support • support@quantilecull.com
    </div>
  </div>
</body>
</html>
  `;

  console.log(`✉️ Dispatching to ${target.email} (${target.name})...`);

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      from: "QuantileCull Team <support@quantilecull.com>",
      to: [target.email],
      reply_to: "support@quantilecull.com",
      subject: subject,
      html: htmlContent
    })
  });

  const data = await response.json();
  if (!response.ok) {
    console.error(`❌ Failed to send to ${target.email}:`, data);
  } else {
    console.log(`✅ Dispatched to ${target.email}! ID: ${data.id}`);
  }
}

async function run() {
  console.log(`🚀 Starting Cloud Conversion Dispatch to ${targets.length} studios...`);
  for (const t of targets) {
    await sendEmail(t);
  }
  console.log("🏁 All emails dispatched successfully!");
}

run().catch(console.error);
