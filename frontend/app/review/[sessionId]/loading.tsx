import { PageLayout } from "@/components/shared/page-layout";
import { ReviewEditorSkeleton } from "@/components/shared/loading-skeletons";

export default function Loading() {
  return (
    <PageLayout showBackButton backHref="/sessions">
      <ReviewEditorSkeleton />
    </PageLayout>
  );
}
