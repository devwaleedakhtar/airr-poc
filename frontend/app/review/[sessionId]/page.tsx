import { getSession } from "@/lib/api";
import ReviewTabs from "@/components/review/review-tabs";

type Props = { params: Promise<{ sessionId: string }> };

export default async function ReviewPage({ params }: Props) {
  const { sessionId } = await params;
  const session = await getSession(sessionId);
  return <ReviewTabs session={session} />;
}
