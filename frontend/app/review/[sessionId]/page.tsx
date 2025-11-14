import { getSession } from "@/lib/api";
import ReviewEditor from "@/components/review/review-editor";

type Props = { params: Promise<{ sessionId: string }> };

export default async function ReviewPage({ params }: Props) {
  const { sessionId } = await params;
  const session = await getSession(sessionId);
  return (
    <main className="mx-auto max-w-5xl py-10 px-4">
      <ReviewEditor session={session} />
    </main>
  );
}
