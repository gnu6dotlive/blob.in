/*
 * BLOB-AC-05 isolated Weston test-input module (original harness code).
 * Loads ONLY in test Weston with BLOB_AC05_ISOLATED_COMPOSITOR=1.
 * Uses libweston APIs to emit compositor-origin pointer events.
 * Does NOT interact with the user's Hyprland session or real /dev/input.
 */
#define _POSIX_C_SOURCE 200809L
#include <libweston/libweston.h>
#include <wayland-server-core.h>
#include <linux/input-event-codes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Weston 15 internal input entry points, tied to the host's installed 15.0.1 ABI. */
void weston_seat_init(struct weston_seat *seat, struct weston_compositor *ec,
                      const char *seat_name);
int weston_seat_init_pointer(struct weston_seat *seat);
void notify_motion_absolute(struct weston_seat *seat, const struct timespec *time,
                            double x, double y);
void notify_button(struct weston_seat *seat, const struct timespec *time,
                   int32_t button, enum wl_pointer_button_state state);
void notify_pointer_frame(struct weston_seat *seat);

struct fixture {
    struct weston_compositor *compositor;
    struct weston_seat seat;
    struct wl_event_source *timer;
    int stage;
};
static int input_tick(void *data) {
    struct fixture *f = data;
    struct timespec stamp;
    clock_gettime(CLOCK_MONOTONIC, &stamp);
    /* Pointer moves on the PRODUCTION showcase Primitive lab canvas.
     * Weston kiosk output is 1280x800; canvas width 932, circle id=1
     * is near x=258 y=400; 140px drag. No production app code injected. */
    switch (f->stage) {
    case 0:
        notify_motion_absolute(&f->seat, &stamp, 258.0, 400.0);
        fprintf(stderr, "BLOB_AC05_COMPOSITOR_STEP enter A x258 y400\n");
        break;
    case 1:
        notify_button(&f->seat, &stamp, BTN_LEFT, WL_POINTER_BUTTON_STATE_PRESSED);
        fprintf(stderr, "BLOB_AC05_COMPOSITOR_STEP down A\n");
        break;
    case 2:
        notify_motion_absolute(&f->seat, &stamp, 318.0, 400.0);
        fprintf(stderr, "BLOB_AC05_COMPOSITOR_STEP preview dx60\n");
        break;
    case 3:
        notify_motion_absolute(&f->seat, &stamp, 398.0, 400.0);
        fprintf(stderr, "BLOB_AC05_COMPOSITOR_STEP preview dx140\n");
        break;
    case 4:
        notify_button(&f->seat, &stamp, BTN_LEFT, WL_POINTER_BUTTON_STATE_RELEASED);
        fprintf(stderr, "BLOB_AC05_COMPOSITOR_STEP up A\n");
        break;
    default:
        fprintf(stderr, "BLOB_AC05_COMPOSITOR_STEP finished\n");
        return 0;
    }
    notify_pointer_frame(&f->seat);
    fflush(stderr);
    f->stage++;
    wl_event_source_timer_update(f->timer, 550);
    return 0;
}
WL_EXPORT int weston_module_init(struct weston_compositor *ec) {
    const char *gate = getenv("BLOB_AC05_ISOLATED_COMPOSITOR");
    const char *sock = getenv("WAYLAND_DISPLAY");
    if (!gate || strcmp(gate, "1") != 0 || !sock || strncmp(sock, "blob-ac05-private-", 18) != 0) {
        fprintf(stderr,"BLOB_AC05_REFUSED_NOT_ISOLATED\n");
        return -1;
    }
    struct fixture *f = calloc(1, sizeof(*f));
    if (!f) return -1;
    f->compositor = ec;
    weston_seat_init(&f->seat, ec, "ac03-private-seat");
    if (weston_seat_init_pointer(&f->seat) < 0) {
        fprintf(stderr, "BLOB_AC05_POINTER_INIT_FAILED\n");
        return -1;
    }
    struct wl_event_loop *loop = wl_display_get_event_loop(ec->wl_display);
    f->timer = wl_event_loop_add_timer(loop, input_tick, f);
    if (!f->timer) return -1;
    wl_event_source_timer_update(f->timer, 4800);
    fprintf(stderr, "BLOB_AC05_PRIVATE_SEAT_READY\n");
    fflush(stderr);
    return 0;
}

WL_EXPORT int wet_module_init(struct weston_compositor *ec, int *argc, char *argv[]) {
    (void)argc; (void)argv;
    return weston_module_init(ec);
}
