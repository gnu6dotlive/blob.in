/* Private CP-JA7B Weston module.
 * Repositions only mapped 512x384 surfaces owned by our exact test viewer.
 * Does not touch shell clients, user's compositor, or any system files.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <unistd.h>
#include <math.h>
#include <wayland-server-core.h>
#include <libweston/libweston.h>
#include <weston/weston.h>
struct control {
    struct weston_compositor *compositor;
    struct wl_event_source *timer;
    unsigned int last_count;
};
static int is_test_view(struct weston_view *v, unsigned int *id) {
    if (!v || !v->surface || !v->surface->resource) return 0;
    if (v->surface->width != 512 || v->surface->height != 384) return 0;
    if (!weston_view_is_mapped(v)) return 0;
    struct wl_client *client=wl_resource_get_client(v->surface->resource);
    pid_t pid=0;
    uid_t uid=0;
    gid_t gid=0;
    wl_client_get_credentials(client,&pid,&uid,&gid);
    if (uid != getuid() || pid<=0) return 0;
    char path[64], exe[PATH_MAX];
    snprintf(path,sizeof(path),"/proc/%ld/exe",(long)pid);
    ssize_t n=readlink(path,exe,sizeof(exe)-1);
    if (n<0) return 0;
    exe[n]=0;
    if (!strstr(exe,"/qchain_cpja7_dual_viewer")) return 0;
    *id=wl_resource_get_id(v->surface->resource);
    return 1;
}

static int tile_now(void *arg) {
    struct control *state=arg;
    struct weston_view *view;
    struct weston_view *first=NULL,*second=NULL;
    unsigned int first_id=UINT_MAX,second_id=UINT_MAX;
    unsigned int id;
    wl_list_for_each(view,&state->compositor->view_list,link) {
        if (!is_test_view(view,&id)) continue;
        if (id<first_id) {
            second=first; second_id=first_id;
            first=view; first_id=id;
        } else if (id<second_id) {
            second=view; second_id=id;
        }
    }
    struct weston_view *windows[2]={first,second};
    const float xs[2]={92.0f,810.0f};
    const float ys[2]={190.0f,190.0f};
    unsigned int count=first?1:0;
    if (second) count++;
    for (unsigned int i=0;i<count;i++) {
        struct weston_view *v=windows[i];
        struct weston_coord_global before=weston_view_get_pos_offset_global(v);
        if (fabs(before.c.x-xs[i])>0.1 ||
            fabs(before.c.y-ys[i])>0.1) {
            struct weston_coord_global pos={.c={xs[i],ys[i]}};
            weston_view_set_position(v,pos);
            weston_view_update_transform(v);
            weston_view_schedule_repaint(v);
        }
    }
    if (count!=state->last_count) {
        fprintf(stderr,"CPJA7B_TILE_VIEWS count=%u primary_id=%u secondary_id=%u\n",
                count,first_id,second_id);
        state->last_count=count;
    }
    wl_event_source_timer_update(state->timer,25);
    return 0;
}
WL_EXPORT int wet_module_init(struct weston_compositor *ec,
                              int *argc,char *argv[]) {
    (void)argc;
    (void)argv;
    struct control *state=calloc(1,sizeof(*state));
    if (!state) return -1;
    state->compositor=ec;
    state->timer=wl_event_loop_add_timer(
          wl_display_get_event_loop(ec->wl_display),tile_now,state);
    if (!state->timer) {free(state);return -1;}
    wl_event_source_timer_update(state->timer,25);
    fprintf(stderr,"CPJA7B_TILE_PLUGIN_ACTIVE\n");
    return 0;
}
