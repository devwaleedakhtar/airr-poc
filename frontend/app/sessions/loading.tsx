import { PageLayout } from "@/components/shared/page-layout";
import { SessionsListSkeleton } from "@/components/shared/loading-skeletons";

export default function Loading() {
  return (
    <PageLayout maxWidth="lg">
      <SessionsListSkeleton />
    </PageLayout>
  );
}
