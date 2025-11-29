"use client";

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import "./CommandPalette.css";

import { TOGGLE_THEME_EVENT } from "./ThemeToggle";

interface CommandEntry {
  label: string;
  href?: string;
  description?: string;
  shortcut?: string;
  keywords?: string;
  external?: boolean;
  action?: () => void;
}

const NAVIGATION_COMMANDS: CommandEntry[] = [
  { label: "Dashboard", href: "/dashboard", keywords: "home overview" },
  { label: "Search", href: "/search", keywords: "find query" },
  { label: "Upload", href: "/upload", keywords: "ingest import" },
  { label: "Settings", href: "/settings", keywords: "config preferences" },
];

const ACTION_COMMANDS: CommandEntry[] = [
  {
    label: "Toggle theme",
    description: "Switch between light and dark modes",
    keywords: "appearance color dark light",
    action: () => {
      window.dispatchEvent(new Event(TOGGLE_THEME_EVENT));
    },
  },
];

export const COMMAND_PALETTE_TOGGLE_EVENT = "exegesis:command-palette-toggle";

export default function CommandPalette(): JSX.Element {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const toggle = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTypingContext = target?.closest("input, textarea, [contenteditable=true]");

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k" && !isTypingContext) {
        event.preventDefault();
        setOpen((previous) => !previous);
      }
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("keydown", toggle);
    return () => window.removeEventListener("keydown", toggle);
  }, []);

  useEffect(() => {
    const handleToggleEvent = () => setOpen((previous) => !previous);

    window.addEventListener(COMMAND_PALETTE_TOGGLE_EVENT, handleToggleEvent);
    return () => window.removeEventListener(COMMAND_PALETTE_TOGGLE_EVENT, handleToggleEvent);
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  const optimisticStatus = useMemo(() => {
    if (!pendingHref) {
      return "";
    }
    const command = NAVIGATION_COMMANDS.find((entry) => entry.href === pendingHref);
    if (!command) {
      return "";
    }
    return `Navigating to ${command.label}…`;
  }, [pendingHref]);

  const handleSelect = (command: CommandEntry) => {
    if (command.action) {
      command.action();
      setPendingHref(null);
      setOpen(false);
      return;
    }

    const href = command.href;
    if (!href) {
      setOpen(false);
      return;
    }

    if (command.external) {
      window.open(href, "_blank", "noopener,noreferrer");
      setPendingHref(null);
      setOpen(false);
      return;
    }

    setPendingHref(href);
    setOpen(false);
    startTransition(() => {
      router.push(href);
    });
  };

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      setSearchValue("");
      setPendingHref(null);
    }
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={handleOpenChange}
      label="Command menu"
      loop
      className="cmdk-dialog"
    >
      <div role="status" aria-live="polite" aria-atomic="true" className="visually-hidden">
        {isPending ? optimisticStatus : ""}
      </div>
      <Command.Input
        ref={inputRef}
        value={searchValue}
        onValueChange={setSearchValue}
        placeholder="Jump to a page or action…"
        className="cmdk-input"
      />
      <Command.List>
        <Command.Empty>No matches found.</Command.Empty>
        <Command.Group heading="Navigate">
          {NAVIGATION_COMMANDS.map((command) => (
            <Command.Item
              key={command.href}
              value={`${command.label.toLowerCase()} ${command.keywords ?? ""}`.trim()}
              onSelect={() => handleSelect(command)}
              disabled={isPending}
            >
              <span className="cmdk-item__label">
                <span>{command.label}</span>
                {command.description ? (
                  <span className="cmdk-item__description">{command.description}</span>
                ) : null}
              </span>
              {command.shortcut ? <span className="cmdk-item__shortcut">{command.shortcut}</span> : null}
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Quick actions">
          {ACTION_COMMANDS.map((command) => (
            <Command.Item
              key={command.label}
              value={`${command.label.toLowerCase()} ${command.keywords ?? ""}`.trim()}
              onSelect={() => handleSelect(command)}
            >
              <span className="cmdk-item__label">
                <span>{command.label}</span>
                {command.description ? (
                  <span className="cmdk-item__description">{command.description}</span>
                ) : null}
              </span>
            </Command.Item>
          ))}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
