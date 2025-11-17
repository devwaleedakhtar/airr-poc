import { PageLayout } from "@/components/shared/page-layout";
import { DashboardSkeleton } from "@/components/shared/loading-skeletons";

export default function Loading() {
  return (
    <PageLayout>
      <DashboardSkeleton />
    </PageLayout>
  );
}
