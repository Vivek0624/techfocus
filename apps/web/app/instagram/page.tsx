import { Suspense } from "react";
import { InstagramPage } from "@/components/pages/instagram";
import { Loading } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <InstagramPage />
    </Suspense>
  );
}
