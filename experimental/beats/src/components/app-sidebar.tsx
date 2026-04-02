import {
  ChevronRight,
  Home,
  Monitor,
  Mouse,
  RadioTower,
  Tv,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Link, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, useTransition } from "react";
import { getAppVersion } from "../actions/app";
import {
  DISABLED_WEBSOCKET_LABEL,
  getConfiguredBeatsWebSocketUrl,
} from "../config/websocket";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./ui/collapsible";
import { DataRow, SpecChip } from "./beats-shell";
import {
  SidebarFooter,
  SidebarHeader,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "./ui/sidebar";

const configuredWebsocketUrl = getConfiguredBeatsWebSocketUrl();

// Menu items.
const items = {
  topLevel: [
    {
      title: "Home",
      url: "/",
      icon: Home,
    },
    {
      title: "Current Stream",
      url: "/stream",
      icon: Tv,
    },
  ],
  navMain: [
    {
      title: "Display",
      icon: Monitor,
      items: [
        {
          title: "View",
          url: "/",
        },
      ],
    },
    {
      title: "Peripherals",
      icon: Mouse,
      isActive: true,
      items: [
        {
          title: "Connected",
          url: "/peripherals/connected",
        },
        {
          title: "Events",
          url: "/peripherals/events",
        },
        {
          title: "Snapshots",
          url: "/peripherals/snapshots",
        },
      ],
    },
  ],
};

const SIDEBAR_TOP_OFFSET_CLASS = "pt-[52px]";

export function AppSidebar() {
  const [appVersion, setAppVersion] = useState("0.0.0");
  const [, startGetAppVersion] = useTransition();
  const { isMobile, open, setOpenMobile } = useSidebar();
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });

  useEffect(
    () => startGetAppVersion(() => getAppVersion().then(setAppVersion)),
    [],
  );

  const isPathActive = (path: string) =>
    path === "/"
      ? pathname === path
      : pathname === path || pathname.startsWith(`${path}/`);

  const handleNavigate = () => {
    if (isMobile) {
      setOpenMobile(false);
    }
  };

  return (
    <Sidebar
      collapsible="icon"
      variant="floating"
      className={SIDEBAR_TOP_OFFSET_CLASS}
    >
      <SidebarHeader className="gap-2 px-2.5 pt-2 pb-1 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-2 group-data-[collapsible=icon]:pb-2">
        <div className="border-sidebar-border bg-sidebar w-full min-w-0 overflow-hidden border px-3 py-3 group-data-[collapsible=icon]:hidden">
          <div className="flex w-full min-w-0 items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-2">
              <p className="font-tomorrow text-sidebar-foreground/60 text-[0.52rem] tracking-[0.3em] uppercase">
                Beats
              </p>
              <div className="min-w-0">
                <h2 className="font-tomorrow text-sidebar-foreground text-base tracking-[0.18em]">
                  BEATS
                </h2>
                <p className="text-sidebar-foreground/70 font-mono text-[0.62rem] tracking-[0.14em] uppercase">
                  Telemetry Department
                </p>
              </div>
            </div>
            <SpecChip className="shrink-0 self-start px-2 py-0.5 text-[0.62rem]">
              TX-24
            </SpecChip>
          </div>
          <div className="mt-4 grid gap-2 group-data-[collapsible=icon]:hidden">
            <DataRow
              label="Program"
              value="Machine Report"
              className="text-sidebar-foreground grid-cols-1 gap-1"
              valueClassName="break-normal"
            />
            <DataRow
              label="Signal"
              value={configuredWebsocketUrl ?? DISABLED_WEBSOCKET_LABEL}
              className="text-sidebar-foreground grid-cols-1 gap-1"
              valueClassName="break-all"
            />
          </div>
        </div>
        <div
          aria-hidden="true"
          className="hidden min-h-12 w-full group-data-[collapsible=icon]:block"
        />
      </SidebarHeader>
      <SidebarSeparator className="mx-2.5 group-data-[collapsible=icon]:hidden" />
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {items.topLevel.map((item) => (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  asChild
                  tooltip={item.title}
                  isActive={isPathActive(item.url)}
                  className="font-tomorrow text-[0.74rem] tracking-[0.14em] uppercase group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:gap-0 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:text-center group-data-[collapsible=icon]:[&>svg]:mx-auto"
                >
                  <Link to={item.url} onClick={handleNavigate}>
                    {item.icon && <item.icon />}
                    <span className="group-data-[collapsible=icon]:hidden">
                      {item.title}
                    </span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel className="font-tomorrow text-[0.68rem] tracking-[0.16em] uppercase group-data-[collapsible=icon]:hidden">
            Entities
          </SidebarGroupLabel>
          <SidebarMenu>
            {items.navMain.map((item) => (
              <Collapsible
                key={item.title}
                asChild
                defaultOpen={item.isActive}
                className="group/collapsible"
              >
                <SidebarMenuItem>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton
                      tooltip={item.title}
                      isActive={item.items.some((subItem) =>
                        isPathActive(subItem.url),
                      )}
                      className="font-tomorrow text-[0.74rem] tracking-[0.14em] uppercase group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:gap-0 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:text-center group-data-[collapsible=icon]:[&>svg]:mx-auto"
                    >
                      {item.icon && <item.icon />}
                      <span className="group-data-[collapsible=icon]:hidden">
                        {item.title}
                      </span>
                      <ChevronRight className="ml-auto transition-transform duration-200 group-data-[collapsible=icon]:hidden group-data-[state=open]/collapsible:rotate-90" />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="group-data-[collapsible=icon]:hidden">
                    <SidebarMenuSub>
                      {item.items?.map((subItem) => (
                        <SidebarMenuSubItem key={subItem.title}>
                          <SidebarMenuSubButton
                            asChild
                            isActive={isPathActive(subItem.url)}
                          >
                            <Link to={subItem.url} onClick={handleNavigate}>
                              <span>{subItem.title}</span>
                            </Link>
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>
                      ))}
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </SidebarMenuItem>
              </Collapsible>
            ))}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarFooter>
          <div
            className={`border-sidebar-border grid gap-2 border-t px-2 pt-3 pb-1 transition-all duration-100 ${
              open
                ? "translate-x-0 opacity-100"
                : "pointer-events-none -translate-x-6 opacity-0"
            }`}
          >
            <div className="text-sidebar-foreground/70 flex items-center gap-2 text-[0.65rem] tracking-[0.18em] uppercase">
              <RadioTower className="size-3" />
              <span>House Styles</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <SpecChip
                tone="muted"
                className="bg-sidebar px-2 py-0.5 text-[0.62rem]"
              >
                TR-100
              </SpecChip>
              <SpecChip
                tone="muted"
                className="bg-sidebar px-2 py-0.5 text-[0.62rem]"
              >
                Houston Mono
              </SpecChip>
            </div>
            <p className="text-sidebar-foreground/60 font-mono text-[0.68rem] tracking-[0.18em] uppercase">
              Version {appVersion}
            </p>
          </div>
        </SidebarFooter>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  );
}
