import { useEffect, useRef, useState } from "react"
import { motion } from "motion/react"

import { AIBlob } from "@/components/ai-blob"
import { Composer } from "@/components/composer"
import { BLOB_COLORS, BotTurn, UserTurn, type Turn } from "@/components/turn"
import { TooltipProvider } from "@/components/ui/tooltip"
import { MODES, bot, type Mode, type Workbook } from "@/lib/bot"

export default function App() {
  const [version, setVersion] = useState("")
  const [pdfs, setPdfs] = useState<string[]>([])
  const [workbooks, setWorkbooks] = useState<Workbook[]>([])
  const [workbook, setWorkbook] = useState<Workbook | null>(null)
  const [mode, setMode] = useState<Mode>("auto")
  const [turns, setTurns] = useState<Turn[]>([])
  const endRef = useRef<HTMLDivElement>(null)
  const busy = turns.some((turn) => !turn.summary && !turn.error)

  useEffect(() => {
    bot.version().then(setVersion)
    bot.recentWorkbooks().then((list) => {
      setWorkbooks(list)
      setWorkbook((current) => current ?? list[0] ?? null)
    })
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [turns])

  const addPdfs = (paths: string[]) => setPdfs((current) => [...new Set([...current, ...paths])])

  useEffect(() => {
    // A file dropped outside the message box would otherwise open in the window, replacing the app.
    const keepDropsHere = (event: DragEvent) => event.preventDefault()
    window.addEventListener("dragover", keepDropsHere)
    window.addEventListener("drop", keepDropsHere)
    const stopListening = bot.onDroppedPdfs(addPdfs)
    return () => {
      window.removeEventListener("dragover", keepDropsHere)
      window.removeEventListener("drop", keepDropsHere)
      stopListening()
    }
  }, [])

  function selectWorkbook(chosen: Workbook) {
    setWorkbook(chosen)
    setWorkbooks((list) => [chosen, ...list.filter((w) => w.path !== chosen.path)])
  }

  async function run() {
    if (!workbook || pdfs.length === 0 || busy) return
    const id = Date.now()
    const files = pdfs
    setPdfs([])
    setTurns((all) => [...all, { id, files, workbookName: workbook.name, results: [], reading: null }])
    const update = (change: (turn: Turn) => Turn) => setTurns((all) => all.map((t) => (t.id === id ? change(t) : t)))

    try {
      const summary = await bot.run(
        files, workbook, mode,
        (file) => update((t) => ({ ...t, reading: file })),
        (result) => update((t) => ({ ...t, results: [...t.results, result] })),
      )
      // The summary's results are final: "read" rows become added or already-there.
      update((t) => ({ ...t, reading: null, results: summary.results, summary }))
      const updated = { ...workbook, peopleRows: summary.peopleRows }
      setWorkbook(updated)
      setWorkbooks((list) => list.map((w) => (w.path === updated.path ? updated : w)))
    } catch (error) {
      update((t) => ({ ...t, reading: null, error: error instanceof Error ? error.message : String(error) }))
      addPdfs(files) // nothing was written, so put them back for another go
    }
  }

  const modeLabel = MODES.find((m) => m.value === mode)?.label

  return (
    <TooltipProvider delayDuration={400}>
      <div className="flex h-dvh flex-col bg-background">
        <header className="mx-auto flex w-full max-w-[46rem] items-center justify-between px-5 pt-4 pb-2 text-sm">
          <span className="font-medium">
            PDF to Excel Bot {version && <span className="text-muted-foreground font-normal">{version}</span>}
          </span>
          <span className="flex gap-2 text-xs text-muted-foreground">
            <span>{workbook?.name ?? "No workbook"}</span>
            <span>{modeLabel}</span>
          </span>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full w-full max-w-[46rem] flex-col px-5">
            {turns.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="mt-auto space-y-7 pt-10 pb-6">
                {turns.map((turn) => (
                  <section key={turn.id} className="space-y-4">
                    <UserTurn turn={turn} />
                    <BotTurn turn={turn} onRetry={addPdfs} />
                  </section>
                ))}
                <div ref={endRef} />
              </div>
            )}
          </div>
        </main>

        <footer className="mx-auto w-full max-w-[46rem] px-5 pb-4">
          <Composer
            pdfs={pdfs}
            onAddPdfs={() => bot.pickPdfs().then(addPdfs)}
            onAddFolder={() => bot.pickFolder().then(addPdfs)}
            onDropFiles={(files) => addPdfs(bot.pdfsFromDrop(files))}
            onRemovePdf={(path) => setPdfs((current) => current.filter((p) => p !== path))}
            workbook={workbook}
            workbooks={workbooks}
            onSelectWorkbook={selectWorkbook}
            onBrowseWorkbook={() => bot.pickWorkbook().then((chosen) => chosen && selectWorkbook(chosen))}
            mode={mode}
            onModeChange={setMode}
            busy={busy}
            onRun={run}
          />
          <p className="mt-2.5 text-center text-xs text-muted-foreground">
            Rows go into the People tab. A backup is saved before every run, and people already there are skipped.
          </p>
        </footer>
      </div>
    </TooltipProvider>
  )
}

function EmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="m-auto flex flex-col items-center gap-5 py-10 text-center"
    >
      <AIBlob size={132} state="idle" colors={BLOB_COLORS} intro />
      <div className="space-y-1.5">
        <h1 className="text-xl font-medium tracking-tight">Drop property PDFs to add people</h1>
        <p className="text-sm text-muted-foreground">
          Each PDF becomes one row in the People tab of your workbook.
        </p>
      </div>
    </motion.div>
  )
}
