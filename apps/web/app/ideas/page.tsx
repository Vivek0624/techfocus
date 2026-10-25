import { Suspense } from "react";
import { IdeasPage } from "@/components/creator/ideas";
import { Loading } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <IdeasPage />
    </Suspense>
  );
}
