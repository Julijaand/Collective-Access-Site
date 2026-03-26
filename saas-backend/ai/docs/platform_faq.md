# Platform FAQ — Collective Access SaaS

## Subscription & Billing

**Q: What plans are available?**
- **Starter** — 3 users, 10 GB storage, €49/month. Best for small private collectors.
- **Pro** — 10 users, 100 GB storage, €199/month. Best for galleries and small museums.
- **Museum** — Unlimited users, 1 TB storage, €799/month. Best for large institutions.
- **Enterprise** — Custom users, custom storage, custom pricing. Contact us.

**Q: How do I upgrade or downgrade my plan?**
Go to the portal → **Billing** page → click **Upgrade** or **Change Plan**. Changes take effect immediately and are prorated.

**Q: Where can I see my invoices?**
Go to the portal → **Billing** page → scroll down to **Invoice History**. You can download each invoice as a PDF.

**Q: What payment methods are accepted?**
We accept all major credit and debit cards (Visa, Mastercard, American Express) via Stripe.

**Q: What happens if my payment fails?**
Stripe retries the payment automatically. You will receive an email notification. If the payment fails after 3 retries, your instance will be suspended until payment is updated.

---

## Tenant Instances

**Q: How long does provisioning take?**
After a successful payment, your Collective Access instance is provisioned automatically within 2–3 minutes.

**Q: How do I access my Collective Access instance?**
After provisioning, your instance URL appears on the **Overview** page of the portal. Click **Open Instance** to go directly to it.

**Q: Can I have multiple instances?**
Each active subscription gives you one instance. To have multiple, subscribe with multiple accounts or contact us about Enterprise plans.

**Q: What is the installation wizard?**
The first time you visit your instance URL, Collective Access runs a setup wizard to configure the database and create the administrator account. Complete this wizard once — it takes about 2 minutes.

**Q: I see the installer page instead of the login screen. What do I do?**
The setup wizard has not been completed. Navigate to `https://your-instance-url/install/index.php` and complete the installation.

**Q: Can I import existing collection data?**
Yes. Collective Access supports importing from CSV, XML, EAD, and other formats. Use **Manage → Import** inside your instance.

---

## Team Management

**Q: How do I invite team members?**
Go to the portal → **Team** page → click **Invite Member**. Enter their email and assign a role. They will receive an invitation to join.

**Q: What roles can I assign?**
- **Owner** — full portal access, cannot be removed
- **Admin** — full access except removing the owner
- **Editor** — can manage most settings
- **Viewer** — read-only portal access

**Q: Can I remove a team member?**
Yes, go to **Team** → click the three-dot menu next to the member → **Remove**. The owner cannot be removed.

---

## Support

**Q: How do I contact support?**
Open a ticket via the portal → **Support** page → **New Ticket**. Our team responds within 24 hours.

**Q: Can I reply to a resolved ticket?**
Yes — replying to a resolved ticket automatically reopens it.

**Q: What information should I include in a support ticket?**
Include: your instance URL, a description of the issue, steps to reproduce it, and any error messages you see.

---

## Backups

**Q: Are backups automatic?**
Automatic daily backups are planned for production. Currently you can create manual backups from the portal → **Backups** page.

**Q: How do I restore a backup?**
Go to **Backups** → find the backup you want → click **Restore**. You will be asked to confirm. The restore process takes a few minutes.

**Q: How long are backups retained?**
Backups are retained for 30 days by default.
