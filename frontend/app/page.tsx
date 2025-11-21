import { listSessions } from "@/lib/api";
import DashboardOverview from "@/components/dashboard/overview";

export default async function Home() {
  const sessions = await listSessions();
  const recent = sessions.slice(0, 5);
  return <DashboardOverview sessions={recent} />;
}
