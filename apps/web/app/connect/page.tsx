import { Suspense } from "react";
import { ConnectPage } from "@/components/creator/connect";
import { Loading } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <ConnectPage />
    </Suspense>
  );
}
