/*
 * BLOB-UI-RUNTIME-01A isolated Weston test-input module (original harness code).
 * Loads ONLY in test Weston with BLOB_UI_01E_ISOLATED_COMPOSITOR=1.
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
    /* Production Visualization -> Distance action button center x1160 y643.
     * Test-only private Weston pointer; no physical HID or host input. */
    switch (f->stage) {
    case 0:
        notify_motion_absolute(&f->seat, &stamp, 1160.0, 643.0);
        fprintf(stderr, "BLOB_UI01E_COMPOSITOR_MOVE_TO_DISTANCE x1160 y643\n");
        break;
    case 1:
        notify_button(&f->seat, &stamp, BTN_LEFT, WL_POINTER_BUTTON_STATE_PRESSED);
        fprintf(stderr, "BLOB_UI01E_COMPOSITOR_BUTTON_DOWN\n");
        break;
    case 2:
        notify_button(&f->seat, &stamp, BTN_LEFT, WL_POINTER_BUTTON_STATE_RELEASED);
        fprintf(stderr, "BLOB_UI01E_COMPOSITOR_BUTTON_UP\n");
        break;
    case 3:
        notify_motion_absolute(&f->seat, &stamp, 1160.0, 643.0);
        fprintf(stderr, "BLOB_UI01E_COMPOSITOR_MOVE_TO_TOGGLE x975 y670\n");
        break;
    case 4:
        notify_button(&f->seat, &stamp, BTN_LEFT, WL_POINTER_BUTTON_STATE_PRESSED);
        fprintf(stderr, "BLOB_UI01E_COMPOSITOR_TOGGLE_DOWN\n");
        break;
    case 5:
        notify_button(&f->seat, &stamp, BTN_LEFT, WL_POINTER_BUTTON_STATE_RELEASED);
        fprintf(stderr, "BLOB_UI01E_COMPOSITOR_TOGGLE_UP\n");
        break;
    default:
        fprintf(stderr, "BLOB_UI01E_COMPOSITOR_FINISHED\n");
        return 0;
    }
    notify_pointer_frame(&f->seat);
    fflush(stderr);
    f->stage++;
    wl_event_source_timer_update(f->timer, 320);
    return 0;
}
WL_EXPORT int weston_module_init(struct weston_compositor *ec) {
    const char *gate = getenv("BLOB_UI_01E_ISOLATED_COMPOSITOR");
    const char *sock = getenv("WAYLAND_DISPLAY");
    if (!gate || strcmp(gate, "1") != 0 || !sock || strncmp(sock, "blob-ui-01e-private-", 20) != 0) {
        fprintf(stderr,"BLOB_UI01E_REFUSED_NOT_ISOLATED\n");
        return -1;
    }
    struct fixture *f = calloc(1, sizeof(*f));
    if (!f) return -1;
    f->compositor = ec;
    weston_seat_init(&f->seat, ec, "ui01b-private-seat");
    if (weston_seat_init_pointer(&f->seat) < 0) {
        fprintf(stderr, "BLOB_UI01E_POINTER_INIT_FAILED\n");
        return -1;
    }
    struct wl_event_loop *loop = wl_display_get_event_loop(ec->wl_display);
    f->timer = wl_event_loop_add_timer(loop, input_tick, f);
    if (!f->timer) return -1;
    wl_event_source_timer_update(f->timer, 2800);
    fprintf(stderr, "BLOB_UI01E_PRIVATE_SEAT_READY\n");
    fflush(stderr);
    return 0;
}

WL_EXPORT int wet_module_init(struct weston_compositor *ec, int *argc, char *argv[]) {
    (void)argc; (void)argv;
    return weston_module_init(ec);
}
