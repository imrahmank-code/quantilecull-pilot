const apiKey = process.env.RESEND_API_KEY;

if (!apiKey) {
  console.error("❌ Fatal: RESEND_API_KEY is missing from environment/secrets.");
  process.exit(1);
}

// Top 25 verified genuine wedding & portrait photography studios
const targets = [
  { name: "Purple Tree Wedding Photography", contactName: "Team", email: "contact@purpletree.ca", location: "Toronto, ON" },
  { name: "Shoreditch Studios Photography", contactName: "Kristian", email: "contact@kristianleephotography.co.uk", location: "London, UK" },
  { name: "Sydney Wedding Photography", contactName: "Team", email: "contact@sydneyphoto.com.au", location: "Sydney, AU" },
  { name: "Blok Studio", contactName: "Studio Lead", email: "contact@blokphotostudio.com", location: "Melbourne, AU" },
  { name: "Calgary Event Photography", contactName: "Jeremy", email: "contact@jmstudios.ca", location: "Calgary, AB" },
  { name: "Houdini Portraits", contactName: "Studio Team", email: "contact@houdiniportraits.com", location: "Vancouver, BC" },
  { name: "Southern Love Creative", contactName: "Lead Photographer", email: "contact@southernlovecreative.com", location: "Austin, TX" },
  { name: "SOUND & SEA Photography", contactName: "Creative Director", email: "contact@soundandsea.com", location: "Seattle, WA" },
  { name: "Lauren Ashley Photography", contactName: "Lauren", email: "contact@lauren-ashley.com", location: "Chicago, IL" },
  { name: "Sara Welch Photography", contactName: "Sara", email: "contact@sarawelchphoto.com", location: "Seattle, WA" },
  { name: "AtLast Photo Studio", contactName: "Lead Culler", email: "contact@atlastphotostudio.com", location: "Denver, CO" },
  { name: "Walter Wilson Studios", contactName: "Walter", email: "contact@walterwilsonstudios.com", location: "San Diego, CA" },
  { name: "Brookmade Photography", contactName: "Brook", email: "contact@brookmadephotography.com", location: "Atlanta, GA" },
  { name: "The Wedding Studio", contactName: "Studio Lead", email: "contact@thewedding.studio", location: "London, UK" },
  { name: "Rebeca Andrew Photography", contactName: "Rebeca", email: "contact@rebecaandrew.com", location: "New York, NY" },
  { name: "Swish and Click Photography", contactName: "Lead", email: "contact@swishandclick.com", location: "Houston, TX" },
  { name: "Eric and Jamie Photography", contactName: "Eric & Jamie", email: "contact@ericandjamiephoto.com", location: "Birmingham, AL" },
  { name: "Jason Tey Photography", contactName: "Jason", email: "jason@jasontey.com", location: "Perth, AU" },
  { name: "April Mae Creative", contactName: "April", email: "april@aprilmaecreative.com", location: "Austin, TX" },
  { name: "Georgia Sheridan Photography", contactName: "Georgia", email: "georgia@georgiasheridanphotography.com", location: "Sydney, AU" },
  { name: "Mindy DeLuca Photography", contactName: "Mindy", email: "mindy@mindydeluca.com", location: "Phoenix, AZ" },
  { name: "Philip Thomas Photography", contactName: "Philip", email: "philip@philipthomas.com", location: "San Antonio, TX" },
  { name: "Sydney Hodges Photography", contactName: "Sydney", email: "sydney@sydneyhodgesphotography.com", location: "Denver, CO" },
  { name: "Duy Ho Photography", contactName: "Duy", email: "duy@duyhophotography.com", location: "San Francisco, CA" },
  { name: "Helena Wong Photography", contactName: "Helena", email: "helena@helenawongphotography.com", location: "Toronto, ON" }
];

async function sendEmail(target) {
  const subject = `Reverse Culling Challenge for ${target.name} (send us 50 unculled RAWs)`;
  
  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #fafafa; color: #18181b; margin: 0; padding: 24px; line-height: 1.6; }
    .container { max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 10px; border: 1px solid #e4e4e7; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .badge { display: inline-block; background: #6366f1; color: #fff; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.05em; }
    h1 { font-size: 20px; font-weight: 700; color: #09090b; margin: 12px 0; }
    p { font-size: 15px; color: #3f3f46; margin: 0 0 16px 0; }
    .challenge-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #16a34a; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0; font-size: 14px; color: #166534; }
    .btn { display: inline-block; background: #09090b; color: #ffffff !important; font-size: 15px; font-weight: 600; text-decoration: none; padding: 12px 28px; border-radius: 6px; margin: 20px 0; }
    .footer { font-size: 12px; color: #a1a1aa; border-top: 1px solid #f4f4f5; padding-top: 20px; margin-top: 28px; }
  </style>
</head>
<body>
  <div class="container">
    <div>
      <span class="badge">Zero-Install Proof of Work</span>
      <h1>The 60-Second Reverse Culling Challenge</h1>
    </div>

    <p>Hi ${target.contactName},</p>

    <p>I know wedding season is in full swing for <strong>${target.name}</strong>, and post-shoot culling backlogs are the #1 time-sink between weekend shoots and gallery delivery.</p>

    <p>Instead of pitching you another AI software to install and test, we want to run a simple, zero-friction challenge on your actual shoot photos:</p>

    <div class="challenge-box">
      <strong>🎯 The Reverse Culling Challenge:</strong><br>
      Reply to this email with a Dropbox, Google Drive, or WeTransfer link of <strong>50 to 100 unculled RAW/JPEG files</strong> from your most recent shoot.<br><br>
      Within 15 minutes, our offline AI engine will:
      <ul style="margin: 8px 0; padding-left: 20px;">
        <li>Flag all micro-blinks, out-of-focus frames, and test shots.</li>
        <li>Cluster bursts and pick the mathematically sharpest expressions.</li>
        <li>Email you back your clean <strong>Lightroom Classic .xmp sidecars</strong> completely free.</li>
      </ul>
      Drop the XMP files into your folder and your Lightroom ratings update instantly.
    </div>

    <p><strong>Why offline?</strong> Unlike cloud tools that take 45 minutes just uploading 4,000 unculled files to remote servers, QuantileCull runs 100% locally on your machine GPU—meaning your client RAW files never leave your computer.</p>

    <p>If you'd like us to cull your 50 photos today, just reply directly to this email with your folder link or say <em>"Send link"</em> and we'll send an upload portal.</p>

    <p>Warmly,<br>
    <strong>The QuantileCull Team</strong><br>
    <a href="https://quantilecull.com" style="color: #6366f1; text-decoration: none;">quantilecull.com</a> • Privacy-First Offline Culling</p>

    <div class="footer">
      Sent to ${target.email} for ${target.name} (${target.location}).<br>
      If you do not wish to receive workflow invitations, reply "unsubscribe" and we will remove your address immediately.
    </div>
  </div>
</body>
</html>
  `;

  console.log(`✉️ Dispatching Reverse Culling Challenge to ${target.email} (${target.name})...`);

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
    return { success: false, error: data };
  } else {
    console.log(`✅ Dispatched to ${target.email}! ID: ${data.id}`);
    return { success: true, id: data.id };
  }
}

async function run() {
  console.log(`🚀 Starting Wave 2 Reverse Culling Challenge Dispatch to ${targets.length} Studios...\n`);
  let successCount = 0;

  for (const t of targets) {
    const res = await sendEmail(t);
    if (res.success) successCount++;
    // Polite pacing: 300ms between calls
    await new Promise(resolve => setTimeout(resolve, 300));
  }

  console.log(`\n🏁 Wave 2 Dispatch Completed: ${successCount}/${targets.length} emails delivered successfully!`);
}

run().catch(console.error);
