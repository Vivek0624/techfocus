"use client";
import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Wand2, X } from "lucide-react";
import { errorMessage, v2, type Audience, type Caption, type Hook, type HookScore, type Repurpose } from "@/lib/api";
import { CATEGORIES, catLabel } from "@/lib/creator";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { ErrorState, Loading } from "@/components/ui/states";
import { Bar, CopyButton, SaveToIdea, Section, Segmented, Verdict } from "./kit";
import { Explain } from "@/components/ui/explain";
import { Panel, Screen } from "./layout";
import { ReelScriptBlock, ShareabilityCard, VoiceCheck } from "./growth";

type Tab = "hooks" | "caption" | "repurpose";

interface Ctx {
  topic: string;
  audience: Audience;
  hook: string;
  setHook: (h: string) => void;
  setTab: (t: Tab) => void;
  ideaId: number | null;
  category: string;
  setCategory: (c: string) => void;
  setIdeaId: (id: number | null) => void;
}

export function CreatePage() {
  const params = useSearchParams();
  const ideaParam = Number(params?.get("idea")) || null;
  const topicParam = params?.get("topic") ?? "";
  const hookParam = params?.get("hook") ?? "";
  const catParam = params?.get("category") ?? "";
  const initialTab = (params?.get("tab") as Tab) || "hooks";
  const [tab, setTab] = React.useState<Tab>(["hooks", "caption", "repurpose"].includes(initialTab) ? initialTab : "hooks");
  const [topic, setTopic] = React.useState(topicParam);
  const [audience, setAudience] = React.useState<Audience>("beginner");
  const [hook, setHook] = React.useState(hookParam);
  const [category, setCategory] = React.useState((CATEGORIES as readonly string[]).includes(catParam) ? catParam : "tech_concepts");
  const [ideaId, setIdeaId] = React.useState<number | null>(ideaParam);
  const [ideaTitle, setIdeaTitle] = React.useState<string | null>(null);
  const [loadErr, setLoadErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!ideaParam) return;
    let alive = true;
    v2.idea(ideaParam)
      .then((i) => {
        if (!alive) return;
        setTopic((t) => t || i.title);
        setIdeaTitle(i.title);
        if (i.recommended_hook) setHook((h) => h || (i.recommended_hook ?? ""));
        if (i.pillar) setCategory(i.pillar);
      })
      .catch((e) => alive && setLoadErr(errorMessage(e)));
    return () => {
      alive = false;
    };
  }, [ideaParam]);

  const ctx: Ctx = { topic: topic.trim(), audience, hook, setHook, setTab, ideaId, category, setCategory, setIdeaId };

  return (
    <Screen title="Create" sub="Turn one idea into a hook, a script, a caption and more posts.">
      {loadErr && <ErrorState message={loadErr} />}
      <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-[minmax(260px,320px)_minmax(0,1fr)]">
        <Panel title="Your reel" what="Start here. Everything on the right uses this." todo={topic.trim() ? "Now pick a step on the left." : "Type what the reel is about."}>
          <div className="flex flex-col gap-3">
            {ideaTitle && (
              <p className="text-xs text-muted">
                Working on idea: <span className="text-fg">{ideaTitle}</span>
              </p>
            )}
            <Field label="What's the post about?" htmlFor="topic">
              <Input id="topic" className="h-10" placeholder="e.g. APIs, explained with a chai order" value={topic} onChange={(e) => setTopic(e.target.value)} />
            </Field>
            <div>
              <p className="mb-1 text-xs font-medium text-muted">Who is watching?</p>
              <Segmented
                label="Audience"
                value={audience}
                onChange={setAudience}
                options={[
                  { value: "beginner", label: "Beginners" },
                  { value: "developer", label: "Developers" },
                ]}
              />
            </div>
            {hook && (
              <div className="rounded-xl bg-panel-2 p-2.5 text-xs">
                <p className="flex items-center justify-between text-muted">
                  <Explain term="hook">Your hook</Explain>
                  <button type="button" aria-label="Clear hook" onClick={() => setHook("")} className="hover:text-fg">
                    <X className="size-3.5" />
                  </button>
                </p>
                <p className="mt-0.5 text-sm text-fg">“{hook}”</p>
              </div>
            )}
            <div role="tablist" aria-label="Create" className="mt-1 flex flex-col gap-1">
              {(
                [
                  ["hooks", "Hooks", "1. Pick the first line + get a script"],
                  ["caption", "Caption", "2. Text under the post + hashtags"],
                  ["repurpose", "Repurpose", "3. Same idea as carousel, LinkedIn, Short"],
                ] as [Tab, string, string][]
              ).map(([k, l, sub]) => (
                <button
                  key={k}
                  role="tab"
                  type="button"
                  aria-selected={tab === k}
                  aria-label={l}
                  onClick={() => setTab(k)}
                  className={cn("rounded-xl px-3 py-2 text-left", tab === k ? "bg-panel-2" : "hover:bg-panel-2/60")}
                >
                  <span className={cn("block text-sm", tab === k ? "font-semibold" : "")}>{l}</span>
                  <span className="block text-[11px] text-muted">{sub}</span>
                </button>
              ))}
            </div>
          </div>
        </Panel>
        <Panel
          title={tab === "hooks" ? "Hooks & script" : tab === "caption" ? "Caption" : "Repurpose"}
          what={
            tab === "hooks"
              ? "The first 1-2 seconds decide if people keep watching. Pick one, then build the script."
              : tab === "caption"
                ? "Only the first ~125 characters show before '… more'. Make them count."
                : "Get 5 posts out of one idea."
          }
        >
          {/* All tabs stay mounted so switching tabs never throws away generated work. */}
          <div hidden={tab !== "hooks"}><HooksTab ctx={ctx} /></div>
          <div hidden={tab !== "caption"}><CaptionTab ctx={ctx} /></div>
          <div hidden={tab !== "repurpose"}><RepurposeTab ctx={ctx} /></div>
        </Panel>
      </div>
    </Screen>
  );
}

function SourceHint({ source }: { source?: string }) {
  if (!source) return null;
  return (
    <p className="mt-4 text-xs text-muted/80">
      Written by: {source === "bedrock" ? "AI model" : "templates"}
      {source === "template" && (
        <>
          {" "}· Connect Bedrock in <Link href="/settings" className="underline">Settings → Advanced</Link> for model-written versions.
        </>
      )}
    </p>
  );
}

function NeedTopic() {
  return <p className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">Type a topic above to start.</p>;
}

// ---------- Hooks ----------
const PERSPECTIVES = [
  { value: "third", label: "Third-person" },
  { value: "you", label: "“You”" },
  { value: "i", label: "“I”" },
];

function HooksTab({ ctx }: { ctx: Ctx }) {
  const [perspective, setPerspective] = React.useState("third");
  const [res, setRes] = React.useState<{ source: string; hooks: Hook[]; note?: string } | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const run = async () => {
    if (!ctx.topic) return;
    setBusy(true);
    setErr(null);
    try {
      setRes(await v2.hooks({ topic: ctx.topic, audience: ctx.audience, perspective }));
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const hooks = [...(res?.hooks ?? [])].sort((a, b) => b.score - a.score);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Perspective" value={perspective} onChange={setPerspective} options={PERSPECTIVES} />
        <Button onClick={run} disabled={busy || !ctx.topic} className="h-9">
          <Wand2 /> {busy ? "Writing…" : res ? "Write new hooks" : "Write hooks"}
        </Button>
      </div>
      {err && <ErrorState message={err} onRetry={run} />}
      {!ctx.topic && !res && <NeedTopic />}
      {busy && !res && <Loading label="Writing hooks…" />}
      {res && (
        <div>
          <ol className="flex flex-col gap-3" data-testid="hook-list">
            {hooks.map((h) => (
              <li key={h.text} className={cn("rounded-xl border bg-panel p-4", ctx.hook === h.text ? "border-accent" : "border-line")}>
                <div className="flex items-start justify-between gap-3">
                  <p className="text-base font-medium leading-snug" data-testid="hook-text">
                    {h.text}
                  </p>
                  <Verdict verdict={h.verdict} score={h.score} />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                  <Badge>{h.formula}</Badge>
                  <span>On screen: {h.on_screen}</span>
                </div>
                <Bar value={h.score} className="mt-3" />
                {h.fix && <p className="mt-2 text-xs text-muted">{h.fix.replace(/^Weakest: /, "To improve: ")}</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  <CopyButton text={h.text} />
                  <Button
                    size="sm"
                    variant={ctx.hook === h.text ? "default" : "outline"}
                    onClick={() => {
                      ctx.setHook(h.text);
                      toast.success("Hook set. Write the caption next.", { action: { label: "Caption", onClick: () => ctx.setTab("caption") } });
                    }}
                  >
                    {ctx.hook === h.text ? "Using this" : "Use this"}
                  </Button>
                  <SaveToIdea ideaId={ctx.ideaId} defaultTitle={ctx.topic} payload={{ hook: h.text, category: ctx.category }} onSaved={(id) => id && ctx.setIdeaId(id)} />
                </div>
              </li>
            ))}
          </ol>
          {res.note && <p className="mt-3 text-xs text-muted">{res.note}</p>}
          <SourceHint source={res.source} />
        </div>
      )}
      <TestHook perspective={perspective} />
      <ShareabilityCard text={ctx.hook || ctx.topic} category={ctx.category} />
    </div>
  );
}

const CHECK_LABEL: Record<string, string> = { LENGTH: "Short enough", SPECIFICITY: "Specific", STAKES: "Something at stake", FRONTLOAD: "Gets to the point", ADDRESS: "Talks to the viewer" };

function TestHook({ perspective }: { perspective: string }) {
  const [text, setText] = React.useState("");
  const [r, setR] = React.useState<HookScore | null>(null);
  const [busy, setBusy] = React.useState(false);
  return (
    <Section title="Test your own hook" sub="Paste the first line you plan to say. We'll score it in a second.">
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!text.trim()) return;
          setBusy(true);
          try {
            setR(await v2.scoreHook({ text: text.trim(), perspective }));
          } catch (err) {
            toast.error(errorMessage(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Input aria-label="Your hook" placeholder="Stop learning Python like this" value={text} onChange={(e) => setText(e.target.value)} className="h-10" />
        <Button type="submit" variant="secondary" className="h-10" disabled={busy || !text.trim()}>
          Score it
        </Button>
      </form>
      {r && (
        <div className="mt-4" data-testid="hook-score">
          <div className="flex items-center gap-3">
            <span className="text-3xl font-semibold">{r.score}</span>
            <Verdict verdict={r.verdict} />
            {r.formula && <Badge>{r.formula}</Badge>}
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {Object.entries(r.checks).map(([k, c]) => (
              <div key={k} title={c.detail}>
                <div className="flex justify-between text-xs">
                  <span>{CHECK_LABEL[k] ?? k}</span>
                  <span className="text-muted">{c.score}</span>
                </div>
                <Bar value={c.score} className="mt-1" dim={c.score < 50} />
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted">{r.fix ? r.fix.replace(/^Weakest: /, "Fix this first: ") : "Looks good. Say it fast and in the first second."}</p>
        </div>
      )}
    </Section>
  );
}

// ---------- Caption ----------
function CaptionTab({ ctx }: { ctx: Ctx }) {
  const [res, setRes] = React.useState<Caption | null>(null);
  const [tags, setTags] = React.useState<string[]>([]);
  const [expanded, setExpanded] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const run = async () => {
    if (!ctx.topic) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await v2.caption({ topic: ctx.topic, hook: ctx.hook || null, category: ctx.category, audience: ctx.audience });
      setRes(r);
      setTags(r.hashtags);
      setExpanded(false);
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  // Full caption with the user's current hashtag selection.
  const text = React.useMemo(() => {
    if (!res) return "";
    const without = res.hashtags.length ? res.full.replace(res.hashtags.join(" "), "").trimEnd() : res.full;
    return tags.length ? `${without}\n\n${tags.join(" ")}` : without;
  }, [res, tags]);
  const max = res?.max ?? 2200;
  const cut = res?.preview_cut.replace(/\.\.\. more$/, "").trimEnd() ?? "";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Topic group" htmlFor="cap-cat">
          <Select id="cap-cat" value={ctx.category} onChange={(e) => ctx.setCategory(e.target.value)} className="w-48">
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {catLabel(c)}
              </option>
            ))}
          </Select>
        </Field>
        <Button onClick={run} disabled={busy || !ctx.topic}>
          <Wand2 /> {busy ? "Writing…" : res ? "Rewrite caption" : "Write caption"}
        </Button>
      </div>
      {!ctx.hook && <p className="text-xs text-muted">Tip: pick a hook in the Hooks tab first; the caption will open with it.</p>}
      {err && <ErrorState message={err} onRetry={run} />}
      {!ctx.topic && !res && <NeedTopic />}
      {res && (
        <div className="grid gap-6 md:grid-cols-[minmax(0,380px)_1fr]">
          <div className="rounded-xl border border-line bg-black/40 p-4" data-testid="ig-preview">
            <div className="mb-3 flex items-center gap-2">
              <div className="size-8 rounded-full bg-gradient-to-tr from-amber-400 via-pink-500 to-violet-500 p-[2px]">
                <div className="size-full rounded-full bg-panel" />
              </div>
              <span className="text-sm font-semibold">vivek_techfocus</span>
            </div>
            <div className="mb-3 aspect-[4/5] rounded-lg bg-panel-2" aria-hidden />
            <p className="whitespace-pre-line text-sm">
              <span className="font-semibold">vivek_techfocus </span>
              {expanded ? (
                text
              ) : (
                <>
                  {cut}
                  <button type="button" className="text-muted" onClick={() => setExpanded(true)}>
                    ... more
                  </button>
                </>
              )}
            </p>
          </div>
          <div className="flex flex-col gap-4">
            <p className={cn("text-sm", text.length > max ? "text-red-400" : "text-muted")} data-testid="char-count">
              {text.length} / {max} characters
            </p>
            <p className="text-xs text-muted">The first line is all people see before “... more”. Make it count.</p>
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Hashtags (tap × to remove)</p>
              <div className="flex flex-wrap gap-1.5">
                {tags.map((t) => (
                  <span key={t} className="inline-flex items-center gap-1 rounded-full bg-panel-2 px-2.5 py-1 text-xs">
                    {t}
                    <button type="button" aria-label={`Remove ${t}`} onClick={() => setTags(tags.filter((x) => x !== t))} className="text-muted hover:text-fg">
                      <X className="size-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
            {res.keywords.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Search words people type</p>
                <p className="text-sm text-muted">{res.keywords.join(" · ")}</p>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <CopyButton text={text} label="Copy caption" variant="default" size="default" />
              <CopyButton text={tags.join(" ")} label="Copy hashtags" size="default" />
              <SaveToIdea ideaId={ctx.ideaId} defaultTitle={ctx.topic} payload={{ caption: text, hashtags: tags, hook: ctx.hook || null, category: ctx.category }} onSaved={(id) => id && ctx.setIdeaId(id)} />
            </div>
            <VoiceCheck text={text} />
            <SourceHint source={res.source} />
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- Repurpose ----------
function RepurposeTab({ ctx }: { ctx: Ctx }) {
  const [res, setRes] = React.useState<Repurpose | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const ranFor = React.useRef<string | null>(null);

  const run = React.useCallback(async () => {
    if (!ctx.topic) return;
    setBusy(true);
    setErr(null);
    try {
      setRes(await v2.repurpose({ topic: ctx.topic, audience: ctx.audience, hook: ctx.hook || null, idea_id: ctx.ideaId }));
      ranFor.current = ctx.audience;
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [ctx.topic, ctx.audience, ctx.hook, ctx.ideaId]);

  // Audience toggle re-runs ("Rewrite for developers").
  React.useEffect(() => {
    if (res && ranFor.current && ranFor.current !== ctx.audience) run();
  }, [ctx.audience, res, run]);

  const reelText = res ? res.reel_30s.map((b) => `[${b.t}] ${b.say}\nOn screen: ${b.screen}`).join("\n\n") : "";
  const carouselText = res ? res.carousel.map((s, i) => `Slide ${i + 1}: ${s.title}\n${s.text}`).join("\n\n") : "";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={run} disabled={busy || !ctx.topic}>
          <Wand2 /> {busy ? "Writing…" : res ? "Rewrite" : "Turn into 5 posts"}
        </Button>
        {res && <span className="text-xs text-muted">Written for {res.audience === "developer" ? "developers" : "beginners"}. Switch the audience above to rewrite.</span>}
      </div>
      {err && <ErrorState message={err} onRetry={run} />}
      {!ctx.topic && !res && <NeedTopic />}
      {ctx.topic && <ReelScriptBlock topic={ctx.topic} audience={ctx.audience} hook={ctx.hook} category={ctx.category} />}
      {res && (
        <>
          <Block title="30-second Reel" copy={reelText}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th className="py-1 pr-3 font-medium">When</th>
                    <th className="py-1 pr-3 font-medium">Say</th>
                    <th className="py-1 font-medium">On screen</th>
                  </tr>
                </thead>
                <tbody>
                  {res.reel_30s.map((b) => (
                    <tr key={b.t} className="border-t border-line/60 align-top">
                      <td className="whitespace-nowrap py-2 pr-3 text-muted">{b.t}</td>
                      <td className="py-2 pr-3">{b.say}</td>
                      <td className="py-2 text-xs font-medium uppercase text-muted">{b.screen}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Block>
          <Block title="5-slide Carousel" copy={carouselText}>
            <div className="-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-2" data-testid="carousel">
              {res.carousel.map((s, i) => (
                <div key={i} data-testid="slide" className="flex aspect-square w-48 shrink-0 snap-start flex-col justify-between rounded-lg border border-line bg-gradient-to-br from-panel-2 to-bg p-4">
                  <span className="text-[10px] text-muted">{i + 1}/5</span>
                  <div>
                    <p className="text-sm font-semibold leading-snug">{s.title}</p>
                    <p className="mt-1 text-xs text-muted">{s.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </Block>
          <Block title="LinkedIn post" copy={res.linkedin_post}>
            <p className="whitespace-pre-line text-sm">{res.linkedin_post}</p>
          </Block>
          <Block title="YouTube Short script" copy={res.youtube_short}>
            <p className="whitespace-pre-line text-sm">{res.youtube_short}</p>
          </Block>
          <Block title="Text post" copy={res.text_post}>
            <p className="whitespace-pre-line text-sm">{res.text_post}</p>
          </Block>
          <div className="flex flex-wrap items-center gap-2">
            <SaveToIdea
              ideaId={ctx.ideaId}
              defaultTitle={ctx.topic}
              label="Save all 5 to idea"
              payload={{ hook: ctx.hook || res.reel_30s[0]?.say || null, category: ctx.category, package: res as unknown as Record<string, unknown> }}
              onSaved={(id) => id && ctx.setIdeaId(id)}
            />
          </div>
          <SourceHint source={res.source} />
        </>
      )}
    </div>
  );
}

function Block({ title, copy, children }: { title: string; copy: string; children: React.ReactNode }) {
  return (
    <Section title={title} actions={<CopyButton text={copy} />}>
      {children}
    </Section>
  );
}

