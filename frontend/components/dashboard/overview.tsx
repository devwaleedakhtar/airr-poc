import Link from "next/link";
import { Button } from "@/components/ui/button";
import { H1, H3, P } from "@/components/ui/typography";
import type { SessionListItem } from "@/types/extraction";

type Props = {
  sessions: SessionListItem[];
};

export default function DashboardOverview({ sessions }: Props) {
  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <H1>Analyst Dashboard</H1>
        <Button asChild>
          <Link href="/upload">Upload Workbook</Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="rounded border p-5">
          <H3 className="mb-2">Start New Extraction</H3>
          <P>Upload an Excel file, pick a sheet, and extract assumptions.</P>
          <div className="mt-4">
            <Button asChild>
              <Link href="/upload">Go to Upload</Link>
            </Button>
          </div>
        </div>

        <div className="rounded border p-5">
          <H3 className="mb-2">Sessions</H3>
          {sessions.length === 0 ? (
            <P>No sessions yet. Start by uploading a workbook.</P>
          ) : (
            <ul className="divide-y rounded border">
              {sessions.map((s) => (
                <li key={s._id} className="flex items-center justify-between p-3">
                  <div className="space-y-1">
                    <div className="font-medium">{s.sheet_name}</div>
                    <P className="text-xs">{new Date(s.created_at).toLocaleString()}</P>
                  </div>
                  <Button variant="outline" asChild>
                    <Link href={`/review/${s._id}`}>Open</Link>
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 text-right">
            <Button variant="ghost" asChild>
              <Link href="/sessions">View All Sessions</Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

