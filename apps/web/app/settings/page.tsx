import { Suspense } from "react";
import { SettingsPageV2 } from "@/components/creator/settings";
import { Loading } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <SettingsPageV2 />
    </Suspense>
  );
}
