import { Suspense } from "react";
import { InsightsPage } from "@/components/creator/insights";
import { Loading } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <InsightsPage />
    </Suspense>
  );
}
