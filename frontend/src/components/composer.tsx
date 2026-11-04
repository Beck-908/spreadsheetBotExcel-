import { useState, type DragEvent } from "react"
import { ArrowUp, Check, ChevronDown, FileText, FolderOpen, Paperclip, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { MODES, type Mode, type Workbook } from "@/lib/bot"
import { cn } from "@/lib/utils"

const fileName = (path: string) => path.split(/[\\/]/).pop() ?? path

interface ComposerProps {
  pdfs: string[]
  onAddPdfs: () => void
  onAddFolder: () => void
  onDropFiles: (files: File[]) => void
  onRemovePdf: (path: string) => void
  workbook: Workbook | null
  workbooks: Workbook[]
  onSelectWorkbook: (workbook: Workbook) => void
  onBrowseWorkbook: () => void
  mode: Mode
  onModeChange: (mode: Mode) => void
  busy: boolean
  onRun: () => void
}

export function Composer(props: ComposerProps) {
  const { pdfs, workbook, busy } = props
  const [dragging, setDragging] = useState(false)
  const canRun = pdfs.length > 0 && workbook !== null && !busy

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    props.onDropFiles(Array.from(event.dataTransfer.files))
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "rounded-2xl border bg-card/70 shadow-[0_8px_30px_rgb(0_0_0/0.35)] transition-colors",
        dragging && "border-emerald-400/60 bg-emerald-400/5",
      )}
    >
      {pdfs.length === 0 ? (
        <button
          type="button"
          onClick={props.onAddPdfs}
          className="block w-full px-4 pt-3.5 pb-2 text-left text-sm text-muted-foreground"
        >
          {dragging ? "Drop to add these PDFs" : "Drop property PDFs here, or attach them with the clip below"}
        </button>
      ) : (
        <ul className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto px-3 pt-3 pb-1">
          {pdfs.map((path) => (
            <li
              key={path}
              title={path}
              className="flex max-w-56 items-center gap-1.5 rounded-lg border bg-muted/50 py-1 pr-1 pl-2 text-xs"
            >
              <FileText className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{fileName(path)}</span>
              <button
                type="button"
                aria-label={`Remove ${fileName(path)}`}
                onClick={() => props.onRemovePdf(path)}
                className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center gap-1 px-2 pt-1 pb-2">
        <WorkbookPicker {...props} />
        <ModePicker mode={props.mode} onModeChange={props.onModeChange} />
        <IconButton label="Attach PDFs" onClick={props.onAddPdfs}>
          <Paperclip />
        </IconButton>
        <IconButton label="Add a folder of PDFs" onClick={props.onAddFolder}>
          <FolderOpen />
        </IconButton>

        <span className="ml-auto pr-2 text-xs text-muted-foreground tabular-nums">
          {pdfs.length > 0 && `${pdfs.length} PDF${pdfs.length === 1 ? "" : "s"}`}
        </span>
        <Button
          size="icon-sm"
          aria-label="Run"
          disabled={!canRun}
          onClick={props.onRun}
          className="rounded-lg"
        >
          <ArrowUp />
        </Button>
      </div>
    </div>
  )
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={label} onClick={onClick} className="text-muted-foreground">
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

function WorkbookPicker({ workbook, workbooks, onSelectWorkbook, onBrowseWorkbook }: ComposerProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="max-w-48 text-muted-foreground">
          <span className="truncate">{workbook?.name ?? "Choose workbook"}</span>
          <ChevronDown data-icon="inline-end" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Write to workbook</DropdownMenuLabel>
        {workbooks.map((option) => (
          <DropdownMenuItem key={option.path} onSelect={() => onSelectWorkbook(option)} className="gap-2">
            <Check className={cn("size-3.5", option.path === workbook?.path ? "opacity-100" : "opacity-0")} />
            <span className="min-w-0 flex-1">
              <span className="block truncate">{option.name}</span>
              <span className="block truncate text-xs text-muted-foreground">{option.path}</span>
            </span>
            {option.peopleRows !== null && (
              <span className="text-xs text-muted-foreground tabular-nums">{option.peopleRows} people</span>
            )}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onBrowseWorkbook} className="pl-7.5">
          Choose another workbook…
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ModePicker({ mode, onModeChange }: { mode: Mode; onModeChange: (mode: Mode) => void }) {
  const current = MODES.find((option) => option.value === mode) ?? MODES[0]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="text-muted-foreground">
          {current.label}
          <ChevronDown data-icon="inline-end" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel className="text-xs text-muted-foreground">How to write the rows</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={mode} onValueChange={(value) => onModeChange(value as Mode)}>
          {MODES.map((option) => (
            <DropdownMenuRadioItem key={option.value} value={option.value}>
              <span>
                <span className="block">{option.label}</span>
                <span className="block text-xs text-muted-foreground">{option.hint}</span>
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
