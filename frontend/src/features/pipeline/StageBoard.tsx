import { useState } from "react";
import { Mail, MailCheck } from "lucide-react";
import { toast } from "sonner";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiErrorMessage } from "@/lib/apiError";
import { useAdvanceStage, useMappings, useRecordOutcome } from "./api";
import { buildMappingColumns } from "./mappingColumns";
import { ScreeningDialog } from "./ScreeningDialog";
import { JdComposeDialog } from "./JdComposeDialog";
import { CommunicationsPanel } from "./CommunicationsPanel";
import type { Mapping } from "./types";

// Pipeline STAGES only (candidate position) — outcomes live in the "Latest
// outcome" column + the per-application timeline.
const STAGES = [
  { key: "SHORTLISTED", label: "Shortlisted" },
  { key: "JD_EMAIL_SENT", label: "JD Email Sent" },
  { key: "SCREENING_SCHEDULED", label: "Screening Scheduled" },
  { key: "OK_TO_PROCEED", label: "OK to Proceed" },
  { key: "OFFERED", label: "Offer Released" },
  { key: "AWAITING_JOINING", label: "Awaiting Joining" },
];

// Non-hired closing outcomes → prompt "Move candidate to Talent Pool?".
const CLOSING_NONHIRED = new Set(["NO_RESPONSE", "DROPPED", "REJECTED", "OFFER_DECLINED", "WITHDRAWN"]);
// Board action code → engine outcome code (advancing + closing). "OFFERED" is an
// advancing ACTION (Release Offer), handled separately.
const OUTCOME_MAP: Record<string, string> = {
  OK_TO_PROCEED: "PASSED",
  AWAITING_JOINING: "OFFER_ACCEPTED",
  JOINED: "JOINED",
  NO_RESPONSE: "NO_RESPONSE",
  DROPPED: "DROPPED",
  REJECTED: "REJECTED",
  OFFER_DECLINED: "OFFER_DECLINED",
  WITHDRAWN: "WITHDRAWN",
  FAKE: "FAKE",
  BLACKLISTED: "BLACKLISTED",
};

const pretty = (s: string) => s.replace(/_/g, " ").toLowerCase();

export function StageBoard({ reqId }: { reqId: string }) {
  const [tab, setTab] = useState("SHORTLISTED");
  const [screeningTarget, setScreeningTarget] = useState<Mapping | null>(null);
  const [composeMappings, setComposeMappings] = useState<Mapping[] | null>(null);
  const [commsOpen, setCommsOpen] = useState(false);

  const mappings = useMappings(reqId, tab);
  const rows = mappings.data?.results ?? [];
  const recordOutcome = useRecordOutcome();
  const advance = useAdvanceStage();

  function onErr(e: any) {
    toast.error(apiErrorMessage(e, "That action isn't allowed."));
  }

  function doAction(m: Mapping, toStatus: string) {
    if (toStatus === "OFFERED") {
      advance.mutate(
        { mapping: m.mapping_id, action: "RELEASE_OFFER" },
        { onSuccess: () => toast.success(`${m.candidate_name}: offer released.`), onError: onErr },
      );
      return;
    }
    const outcome = OUTCOME_MAP[toStatus] ?? toStatus;
    const move_to_talent_pool = CLOSING_NONHIRED.has(toStatus)
      ? window.confirm("Move candidate to Talent Pool for future opportunities?")
      : false;
    recordOutcome.mutate(
      { mapping: m.mapping_id, outcome, move_to_talent_pool },
      { onSuccess: () => toast.success(`${m.candidate_name}: ${pretty(toStatus)}.`), onError: onErr },
    );
  }

  const columns = buildMappingColumns({
    stage: tab,
    onSendJd: (m) => setComposeMappings([m]),
    onTransition: doAction,
    onScreenings: setScreeningTarget,
  });

  const activeLabel = STAGES.find((s) => s.key === tab)?.label ?? "";

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Screening pipeline</h2>
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Application Stage</p>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          {STAGES.map((s) => (
            <TabsTrigger key={s.key} value={s.key}>
              {s.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {tab === "SHORTLISTED" && rows.length > 0 && (
        <div className="mt-4 flex justify-end">
          <Button size="sm" onClick={() => setComposeMappings(rows)}>
            <Mail className="h-4 w-4" /> Compose JD email ({rows.length})
          </Button>
        </div>
      )}
      <div className="mt-4">
        <DataTable
          columns={columns}
          data={rows}
          isLoading={mappings.isLoading}
          searchPlaceholder="Search candidates…"
          emptyMessage={`No candidates in "${activeLabel}".`}
          toolbar={
            <Button variant="outline" size="sm" onClick={() => setCommsOpen(true)}>
              <MailCheck className="h-4 w-4" /> Communications
            </Button>
          }
        />
      </div>

      {/* Communication tab — every candidate in this requirement's pipeline with
          their latest status; selecting one opens a read-only activity history. */}
      <Dialog open={commsOpen} onOpenChange={setCommsOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Communications</DialogTitle>
            <DialogDescription>
              Candidates in this requirement's pipeline. Select one to view their activity history.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <CommunicationsPanel reqId={reqId} />
          </DialogBody>
        </DialogContent>
      </Dialog>

      <JdComposeDialog
        reqId={reqId}
        mappings={composeMappings ?? []}
        open={!!composeMappings}
        onClose={() => setComposeMappings(null)}
      />
      <ScreeningDialog mapping={screeningTarget} onClose={() => setScreeningTarget(null)} />
    </div>
  );
}
