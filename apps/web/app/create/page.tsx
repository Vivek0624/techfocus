import { Suspense } from "react";
import { CreatePage } from "@/components/creator/create";
import { Loading } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <CreatePage />
    </Suspense>
  );
}
