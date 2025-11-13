import Link from "next/link";
import { listSessions } from "@/lib/api";
import { H1, P } from "@/components/ui/typography";

export default async function SessionsPage() {
  const sessions = await listSessions();
  return (
    <main className="mx-auto max-w-4xl py-10 px-4 space-y-4">
      <H1>Sessions</H1>
      {sessions.length === 0 ? (
        <P>No sessions yet.</P>
      ) : (
        <ul className="divide-y border rounded">
          {sessions.map((s) => (
            <li key={s._id} className="flex items-center justify-between p-3">
              <div className="space-y-1">
                <div className="font-medium">{s.sheet_name}</div>
                <P className="text-xs">{new Date(s.created_at).toLocaleString()}</P>
              </div>
              <Link className="text-primary underline" href={`/review/${s._id}`}>
                View
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

