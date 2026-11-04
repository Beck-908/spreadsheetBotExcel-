import { motion } from "motion/react"
import { Check, Minus, RotateCcw, X } from "lucide-react"

import { AIBlob } from "@/components/ai-blob"
import { Button } from "@/components/ui/button"
import type { PdfResult, RunSummary } from "@/lib/bot"
import { cn } from "@/lib/utils"

export const BLOB_COLORS = ["#16a34a", "#22d3ee", "#4ade80", "#3b82f6"] // Excel greens with a cool edge

export interface Turn {
  id: number
  files: string[] // full paths, as sent
  workbookName: string
  results: PdfResult[]
  reading: string | null // file being read right now
  summary?: RunSummary
  error?: string
}

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })

export function UserTurn({ turn }: { turn: Turn }) {
  const count = turn.files.length
  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="max-w-[85%] rounded-xl border bg-card px-3.5 py-2 text-sm">
        Add {count} PDF{count === 1 ? "" : "s"} to {turn.workbookName}
      </div>
      <p className="max-w-[85%] truncate text-xs text-muted-foreground">
        {turn.files.map((path) => path.split(/[\\/]/).pop()).join("  ·  ")}
      </p>
    </div>
  )
}

export function BotTurn({ turn, onRetry }: { turn: Turn; onRetry: (files: string[]) => void }) {
  const failed = turn.results.filter((r) => r.outcome === "failed")
  return (
    <div className="space-y-3 text-sm leading-relaxed">
      {turn.results.length > 0 && (
        <ul className="divide-y overflow-hidden rounded-xl border">
          {turn.results.map((result, i) => (
            <motion.li
              key={`${i}:${result.file}`} // two folders can hold PDFs with the same name
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
            >
              <ResultRow result={result} />
            </motion.li>
          ))}
        </ul>
      )}

      {turn.reading && (
        <div className="flex items-center gap-2.5 text-muted-foreground">
          <AIBlob size={22} state="thinking" colors={BLOB_COLORS} interactive={false} />
          <span className="animate-pulse">Reading {turn.reading}…</span>
        </div>
      )}

      {turn.summary && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }} className="space-y-2">
          <p>{describe(turn.summary.results, turn.workbookName)}</p>
          {turn.summary.warnings.map((warning) => (
            <p key={warning} className="text-xs text-amber-300/80">{warning}</p>
          ))}
          <p className="text-xs break-all text-muted-foreground">
            {turn.summary.mode === null
              ? "The workbook wasn't touched."
              : turn.summary.mode === "Excel" ? "Written in Excel" : "Written straight to the file"}
            {turn.summary.backup && <> · Backup saved to {turn.summary.backup}</>}
          </p>
          {failed.length > 0 && (
            <Button
              variant="outline"
              size="xs"
              onClick={() => onRetry(turn.files.filter((path) => failed.some((r) => path.endsWith(r.file))))}
            >
              <RotateCcw data-icon="inline-start" />
              Try the {failed.length === 1 ? "failed PDF" : `${failed.length} failed PDFs`} again
            </Button>
          )}
        </motion.div>
      )}

      {turn.error && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-destructive">
          {turn.error} Nothing was written.
        </p>
      )}
    </div>
  )
}

function ResultRow({ result }: { result: PdfResult }) {
  const icon = {
    read: <span className="size-1.5 animate-pulse rounded-full bg-muted-foreground" />,
    added: <Check className="size-3.5 text-emerald-400" />,
    duplicate: <Minus className="size-3.5 text-muted-foreground" />,
    failed: <X className="size-3.5 text-red-400" />,
  }[result.outcome]
  const status = {
    read: "Read",
    added: `Row ${result.row}`,
    duplicate: "Already in sheet",
    failed: "Couldn't read",
  }[result.outcome]
  const details =
    result.outcome === "failed"
      ? [result.reason]
      : [
          `ID ${result.propertyId}`,
          result.value != null ? money.format(result.value) : "no value",
          result.holder,
        ]

  return (
    <div className={cn("flex items-start gap-3 px-3.5 py-2.5", result.outcome === "duplicate" && "opacity-60")}>
      <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{result.name ?? result.file}</p>
        <p className="text-xs text-muted-foreground">
          {details.filter(Boolean).join("  ·  ")}
          {result.missing?.length ? (
            <span className="text-amber-300/80">  ·  No {result.missing.join(" or ").toLowerCase()} in PDF</span>
          ) : null}
        </p>
        {result.notes?.map((note) => (
          <p key={note} className="text-xs text-muted-foreground/70 italic">{note}</p>
        ))}
      </div>
      <span
        className={cn(
          "shrink-0 pt-0.5 text-xs tabular-nums",
          result.outcome === "added" ? "text-emerald-400" : "text-muted-foreground",
          result.outcome === "failed" && "text-red-400",
        )}
      >
        {status}
      </span>
    </div>
  )
}

/** One plain sentence about the run, e.g. "Added 2 people to rows 130–131 … 1 PDF couldn't be read." */
function describe(results: PdfResult[], workbook: string): string {
  const added = results.filter((r) => r.outcome === "added")
  const dupes = results.filter((r) => r.outcome === "duplicate")
  const failed = results.filter((r) => r.outcome === "failed")

  const rows = added.map((r) => r.row!).sort((a, b) => a - b)
  const where = rows.length === 1 ? `row ${rows[0]}` : `rows ${rows[0]}–${rows[rows.length - 1]}`
  const first = added.length
    ? `Added ${added.length === 1 ? "1 person" : `${added.length} people`} to ${where} of the People tab in ${workbook}.`
    : `Nothing new was added to ${workbook}.`

  const rest: string[] = []
  if (dupes.length) rest.push(dupes.length === 1 ? `${dupes[0].name} was already there` : `${dupes.length} people were already there`)
  if (failed.length) rest.push(`${failed.length} PDF${failed.length === 1 ? "" : "s"} couldn't be read`)
  if (!rest.length) return first
  const tail = rest.join(", and ")
  return `${first} ${tail[0].toUpperCase()}${tail.slice(1)}.`
}
