// What the UI asks of the bot. In the desktop app that's the Python bot behind pywebview
// (pdf_excel_bot/desktop.py); under `npm run dev` it's a fake with made-up people, so the UI can be
// previewed in a browser without touching real files.

export type Mode = "auto" | "excel" | "file"

export const MODES: { value: Mode; label: string; hint: string }[] = [
  { value: "auto", label: "Auto", hint: "Use Excel if it's installed, otherwise edit the file" },
  { value: "excel", label: "Excel", hint: "Open Excel and type the rows in" },
  { value: "file", label: "File only", hint: "Edit the workbook file without opening Excel" },
]

export interface Workbook {
  path: string
  name: string
  peopleRows: number | null // rows already in the People tab, when known
}

// "read" means the PDF was read but the workbook hasn't been written yet; the summary settles it.
export type Outcome = "read" | "added" | "duplicate" | "failed"

export interface PdfResult {
  file: string
  outcome: Outcome
  name?: string
  propertyId?: string
  value?: number | null
  holder?: string
  row?: number // People tab row, when added
  missing?: string[] // columns the PDF had nothing for
  notes?: string[] // where a field came from when it wasn't the usual place
  reason?: string // why it failed
}

export interface RunSummary {
  results: PdfResult[]
  backup: string | null
  mode: "Excel" | "file" | null // null: nothing could be read, so the workbook wasn't touched
  peopleRows: number | null // rows in the People tab after the run
  warnings: string[]
}

export interface BotApi {
  version(): Promise<string>
  pickPdfs(): Promise<string[]>
  pickFolder(): Promise<string[]>
  recentWorkbooks(): Promise<Workbook[]>
  pickWorkbook(): Promise<Workbook | null>
  run(pdfs: string[], workbook: Workbook, mode: Mode, onReading: (file: string) => void,
      onResult: (result: PdfResult) => void): Promise<RunSummary>
  /** PDFs from a drop the page saw itself. A web page only gets file names, so only the fake uses this. */
  pdfsFromDrop(files: File[]): string[]
  /** PDFs dropped on the desktop window, with full paths (Python sees those, the page doesn't). */
  onDroppedPdfs(callback: (paths: string[]) => void): () => void
}

const isPdf = (file: File) => file.name.toLowerCase().endsWith(".pdf")

// --- Fake bot for the browser preview -----------------------------------------------------------

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
const fileName = (path: string) => path.split(/[\\/]/).pop() ?? path

const DOWNLOADS = "C:\\Users\\you\\Downloads\\"

type FakePerson = Pick<PdfResult, "name" | "propertyId" | "value" | "holder" | "missing">

// Keyed by file name so a retry or a second run gives the same answer, like the real bot.
const FAKE_PEOPLE: Record<string, FakePerson | null> = {
  "Jordan Avery.pdf": { name: "Jordan Avery", propertyId: "5550001234", value: 12345.67, holder: "EXAMPLE HOLDINGS INC" },
  "Morgan Lee - Profile.pdf": { name: "Morgan Lee", propertyId: "5550002288", value: 1204, holder: "NORTHWIND TRADERS LLC",
    missing: ["Email Address"] },
  "Casey Rivera.pdf": { name: "Casey Rivera", propertyId: "5550003141", value: 880.5, holder: "CONTOSO BANK NA" },
  "scan_0042.pdf": null, // a scan: no text to read
  "Riley Chen.pdf": { name: "Riley Chen", propertyId: "5550004477", value: 56010, holder: "FABRIKAM INSURANCE CO" },
  "Sam Okafor.pdf": { name: "Sam Okafor", propertyId: "5550005902", value: 310.25, holder: "TAILSPIN AIRLINES INC",
    missing: ["Phone Number", "Email Address"] },
}
const fakeSheetIds = new Set(["5550003141"]) // Property IDs already in the fake People tab

const fakeWorkbooks: Workbook[] = [
  { path: "C:\\Users\\you\\Documents\\Company Records.xlsx", name: "Company Records", peopleRows: 128 },
  { path: "C:\\Users\\you\\Documents\\Q4 Leads.xlsx", name: "Q4 Leads", peopleRows: 42 },
]

export const fakeBot: BotApi = {
  async version() {
    return "1.3"
  },
  async pickPdfs() {
    await sleep(250)
    return ["Jordan Avery.pdf", "Morgan Lee - Profile.pdf", "Casey Rivera.pdf", "scan_0042.pdf"].map((f) => DOWNLOADS + f)
  },
  async pickFolder() {
    await sleep(250)
    return ["Riley Chen.pdf", "Sam Okafor.pdf"].map((f) => DOWNLOADS + "October profiles\\" + f)
  },
  async recentWorkbooks() {
    return fakeWorkbooks
  },
  async pickWorkbook() {
    await sleep(250)
    return { path: "C:\\Users\\you\\Desktop\\People 2026.xlsx", name: "People 2026", peopleRows: 7 }
  },
  async run(pdfs, workbook, mode, onReading, onResult) {
    const results: PdfResult[] = []
    let nextRow = (workbook.peopleRows ?? 0) + 2 // header row + existing rows
    for (const pdf of pdfs) {
      const file = fileName(pdf)
      onReading(file)
      await sleep(650)
      const person = FAKE_PEOPLE[file] ?? null
      if (!person) {
        const failed: PdfResult = { file, outcome: "failed",
          reason: "No readable text found. It may be a scanned image, which the bot can't read." }
        results.push(failed)
        onResult(failed)
        continue
      }
      onResult({ ...person, file, outcome: "read" })
      if (fakeSheetIds.has(person.propertyId!)) {
        results.push({ ...person, file, outcome: "duplicate" })
      } else {
        fakeSheetIds.add(person.propertyId!)
        results.push({ ...person, file, outcome: "added", row: nextRow++ })
      }
    }
    await sleep(500) // "writing the workbook"
    const wrote = results.some((r) => r.outcome !== "failed")
    return {
      results,
      backup: wrote ? `${workbook.path.replace(/[^\\]+$/, "")}backups\\${workbook.name}_backup_2026-11-03_214502.xlsx` : null,
      mode: wrote ? (mode === "file" ? "file" : "Excel") : null,
      peopleRows: nextRow - 2,
      warnings: [],
    }
  },
  pdfsFromDrop: (files) => files.filter(isPdf).map((file) => file.name),
  onDroppedPdfs: () => () => {},
}

// --- The real bot, inside the desktop window --------------------------------------------------

type BotEvent = { type: "reading"; file: string } | { type: "read"; result: PdfResult }

interface PyApi {
  version(): Promise<string>
  pick_pdfs(): Promise<string[]>
  pick_folder(): Promise<string[]>
  recent_workbooks(): Promise<Workbook[]>
  pick_workbook(): Promise<Workbook | null>
  run(pdfs: string[], workbook: string, mode: Mode): Promise<{ summary: RunSummary } | { error: string }>
}

declare global {
  interface Window {
    pywebview?: { api: PyApi }
    __botEvent?: (event: BotEvent) => void // Python calls this with progress during a run
    __botDropped?: (paths: string[]) => void // Python calls this with PDFs dropped on the window
  }
}

// pywebview injects its api after the page loads and announces it with "pywebviewready".
const py = new Promise<PyApi>((resolve) => {
  if (window.pywebview?.api) resolve(window.pywebview.api)
  else window.addEventListener("pywebviewready", () => resolve(window.pywebview!.api), { once: true })
})

export const desktopBot: BotApi = {
  version: async () => (await py).version(),
  pickPdfs: async () => (await py).pick_pdfs(),
  pickFolder: async () => (await py).pick_folder(),
  recentWorkbooks: async () => (await py).recent_workbooks(),
  pickWorkbook: async () => (await py).pick_workbook(),
  async run(pdfs, workbook, mode, onReading, onResult) {
    window.__botEvent = (event) => (event.type === "reading" ? onReading(event.file) : onResult(event.result))
    try {
      const reply = await (await py).run(pdfs, workbook.path, mode)
      if ("error" in reply) throw new Error(reply.error)
      return reply.summary
    } finally {
      window.__botEvent = undefined
    }
  },
  pdfsFromDrop: () => [], // the paths arrive through onDroppedPdfs instead
  onDroppedPdfs(callback) {
    window.__botDropped = callback
    return () => {
      window.__botDropped = undefined
    }
  },
}

export const bot: BotApi = import.meta.env.DEV ? fakeBot : desktopBot
