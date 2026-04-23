# Figma + Claude Integration Setup

## Overview
This project uses the **Figma MCP (Model Context Protocol)** to connect Figma designs directly to Claude in VS Code. This allows Claude to read Figma files and generate Next.js components automatically.

---

## Setup Steps (Completed: April 20, 2026)

### 1. Get Figma Personal Access Token
1. Go to [figma.com](https://figma.com) → **Avatar** (top-right) → **Settings**
2. Scroll to **Personal access tokens**
3. Click **Generate new token**
4. Copy the token (format: `figd_...`)

⚠️ **Security:** Never commit this token to git. It's stored securely by VS Code.

---

### 2. Create a Figma File
1. Go to [figma.com](https://figma.com) → **New design file**
2. Or duplicate a template: **Community → search "SaaS dashboard"**
3. Add frames: Press **F** → Select **Desktop** preset (1440 × 1024)
4. Copy the file URL — you'll need the file key

**Example URL:**
```
https://www.figma.com/design/OIn1n5xLKj3MwDa1SyJ4iL/Untitled
                                └─── File Key ───┘
```

**Your Figma File Key:** `OIn1n5xLKj3MwDa1SyJ4iL`

---

### 3. Configure VS Code MCP Server

**File:** `.vscode/mcp.json`

**Note:** The token is stored securely by VS Code — not in the file.

---

### 4. Start the Figma MCP Server

**Option A: From the file**
1. Open `.vscode/mcp.json`
2. Click the **"start"** button that appears above `"servers"`
3. When prompted, paste your Figma token
4. Confirm trust prompt

**Option B: From Command Palette**
1. Press **Cmd+Shift+P**
2. Type `MCP: List Servers`
3. Select **figma** → **Start**
4. Enter your token when prompted

---

### 5. Verify It's Running

**Check server status:**
- Press **Cmd+Shift+P** → `MCP: List Servers`
- You should see **figma** with status: ✅ Running

**Check in Chat:**
- Open **Copilot Chat**
- The Figma tools should be available

---

## Workflow A: Figma Design → Code (new pages)

### 1. Design in Figma
Create a page in Figma (e.g., Billing page with plan cards, invoices table)

### 2. Ask Claude to Generate Code
In Copilot Chat, say:

```
Read Figma file OIn1n5xLKj3MwDa1SyJ4iL and generate the Billing page 
as a Next.js component using shadcn/ui and Tailwind. 
Place it in customer-portal/src/app/(dashboard)/billing/page.tsx
```

### 3. Claude Reads the Design
Claude will:
- Connect to Figma via MCP
- Read the node tree (colors, typography, spacing, layout)
- Generate the Next.js component code
- Create the file in your project

---

## Workflow B: Edit Existing UI in Figma → Apply Changes to Code

Use this when you want to tweak the look of an existing page (colors, layout, etc.) and push those changes back into the codebase.

### Step 1 — Capture the running app into Figma

1. Start the app: `cd customer-portal && npm run dev`
2. Open Chrome → navigate to the page you want to edit (e.g. `http://localhost:3000/dashboard`)
3. Open DevTools → `Cmd+Shift+P` → **"Capture full size screenshot"** → saves a PNG
4. Open Figma → drag the PNG onto the canvas

### Step 2 — Edit visually using Figma Make

1. Select the pasted image in Figma
2. Right-click → **"Send to Figma Make"**
3. When prompted, describe what you want: e.g. `"Recreate this dashboard as editable Figma components"`
4. Figma Make generates a live React preview — make your visual edits there (colors, spacing, etc.)

### Step 3 — Read the changes with Claude

Once you've made edits in Figma Make, Claude can read the generated code directly via the Figma MCP.

In Claude Code (this terminal), just say:
```
Look at my Figma Make design and apply the color changes to the project
```

Claude will:
- Call `get_design_context` or `get_screenshot` via the Figma MCP
- Read the generated `App.tsx` and `theme.css` from Figma Make
- Identify what changed (e.g. background color, button color)
- Apply those values to `customer-portal/src/app/globals.css`

### Step 4 — Verify in browser

Open `http://localhost:3000/dashboard` — changes are live immediately (Next.js hot reload).

---

### Color token reference

Design changes in Figma Make map to these CSS variables in `globals.css`:

| What you changed in Figma | CSS variable to update |
|---|---|
| Page/background color | `--background` |
| Primary buttons | `--primary` |
| Sidebar background | `--sidebar` |
| Muted text / subtitles | `--muted-foreground` |
| Card backgrounds | `--card` |
| Destructive / error red | `--destructive` |
| Borders | `--border` |

**File:** `customer-portal/src/app/globals.css` → `:root { ... }`

### Example — what was applied on 2026-04-23

```css
/* Background changed to pastel blue (Tailwind blue-50) */
--background: #eff6ff;

/* Primary buttons changed to dark navy (Tailwind blue-950) */
--primary: #172554;
```

These were read from Figma Make's `App.tsx`:
- background: `bg-blue-50`
- "Go to Billing" button: `bg-blue-950`

## Project Context

**Customer Portal Stack:**
- Next.js 14 (App Router)
- shadcn/ui components
- Tailwind CSS
- TypeScript

**Existing Components:**
- UI library: `customer-portal/src/components/ui/` (don't modify)
- Dashboard shell: `customer-portal/src/components/dashboard/`

**Where New Pages Go:**
- `customer-portal/src/app/(dashboard)/[page-name]/page.tsx`

---

## Troubleshooting

### Server won't start
- Check that you're using the correct Figma token
- Run: `npx -y figma-developer-mcp --help` to verify the package installs
- Check MCP output: **Cmd+Shift+P** → `MCP: List Servers` → **figma** → **Show Output**

### Token prompt doesn't appear
- Delete the server and re-add it
- Run: **Cmd+Shift+P** → `MCP: Reset Trust`
- Restart VS Code

### Claude can't read the Figma file
- Make sure the file is **not private** (or you're the owner)
- Verify the file key is correct
- Check that the token has proper permissions

## References

- [VS Code MCP Documentation](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)
- [Figma MCP Package](https://www.npmjs.com/package/figma-developer-mcp)
- [Model Context Protocol](https://modelcontextprotocol.io/)


