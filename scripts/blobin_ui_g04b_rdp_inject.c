/* Isolated RDP protocol input sender for Weston compositor qualification.
 * Compiles against the host's installed FreeRDP 3. Input is sent over TCP
 * loopback *inside an unshared network namespace*, never into Hyprland. */
#include <freerdp/freerdp.h>
#include <freerdp/settings.h>
#include <freerdp/settings_keys.h>
#include <freerdp/input.h>
#include <freerdp/scancode.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static BOOL pre_connect(freerdp* instance) { (void)instance; return TRUE; }
static BOOL post_connect(freerdp* instance) { (void)instance; return TRUE; }

static void flush_events(freerdp* instance, int ms) {
    for (int i=0;i<ms/40;i++) {
        (void)freerdp_check_event_handles(instance->context);
        usleep(40000);
    }
}
static int send_mouse(freerdp* client, UINT16 flags, UINT16 x, UINT16 y) {
    int ok=freerdp_input_send_mouse_event(client->context->input,flags,x,y);
    printf("RDP_INJECTION mouse flags=%u x=%u y=%u success=%d\n",flags,x,y,ok);
    fflush(stdout);
    flush_events(client,120);
    return ok;
}
static int send_key(freerdp* client,UINT32 scancode) {
    int ok=freerdp_input_send_keyboard_event_ex(client->context->input,TRUE,FALSE,scancode);
    printf("RDP_INJECTION key_down scancode=%u success=%d\n",scancode,ok);
    fflush(stdout);
    flush_events(client,150);
    ok=ok && freerdp_input_send_keyboard_event_ex(client->context->input,FALSE,FALSE,scancode);
    printf("RDP_INJECTION key_up scancode=%u success=%d\n",scancode,ok);
    fflush(stdout);
    flush_events(client,150);
    return ok;
}
int main(int argc,char** argv) {
    int port=argc==2?atoi(argv[1]):3397;
    freerdp* client=freerdp_new();
    if (!client) return 10;
    client->PreConnect=pre_connect;
    client->PostConnect=post_connect;
    if (!freerdp_context_new(client)) return 11;
    rdpSettings* settings=client->context->settings;
    if (!freerdp_settings_set_string(settings,FreeRDP_ServerHostname,"127.0.0.1")
        || !freerdp_settings_set_uint32(settings,FreeRDP_ServerPort,(UINT32)port)
        || !freerdp_settings_set_string(settings,FreeRDP_Username,"g04b-probe")
        || !freerdp_settings_set_bool(settings,FreeRDP_IgnoreCertificate,TRUE)
        || !freerdp_settings_set_bool(settings,FreeRDP_NlaSecurity,FALSE)
        || !freerdp_settings_set_bool(settings,FreeRDP_NegotiateSecurityLayer,FALSE)
        || !freerdp_settings_set_bool(settings,FreeRDP_ExtSecurity,FALSE)
        || !freerdp_settings_set_bool(settings,FreeRDP_RdpSecurity,TRUE)
        || !freerdp_settings_set_bool(settings,FreeRDP_Authentication,FALSE)
        || !freerdp_settings_set_bool(settings,FreeRDP_TlsSecurity,FALSE)
        || !freerdp_settings_set_bool(settings,FreeRDP_SoftwareGdi,TRUE)) return 12;
    printf("RDP_CONNECTING local_only=1 port=%d\n",port); fflush(stdout);
    if (!freerdp_connect(client)) {
        fprintf(stderr,"RDP_CONNECTION_FAILED code=%u\n",freerdp_get_last_error(client->context));
        return 13;
    }
    printf("RDP_CONNECTED actual_protocol_transport=1\n"); fflush(stdout);
    flush_events(client,1100);
    int success=1;
    success&=send_mouse(client,PTR_FLAGS_MOVE,80,70);
    success&=send_mouse(client,PTR_FLAGS_DOWN|PTR_FLAGS_BUTTON1,80,70);
    success&=send_mouse(client,PTR_FLAGS_BUTTON1,80,70);
    success&=send_mouse(client,PTR_FLAGS_MOVE,270,70);
    success&=send_mouse(client,PTR_FLAGS_DOWN|PTR_FLAGS_BUTTON1,270,70);
    success&=send_mouse(client,PTR_FLAGS_BUTTON1,270,70);
    success&=send_key(client,RDP_SCANCODE_TAB);
    success&=send_key(client,RDP_SCANCODE_RETURN);
    flush_events(client,700);
    printf("RDP_INPUT_SEND_COMPLETE success=%d\n",success); fflush(stdout);
    freerdp_disconnect(client);
    freerdp_context_free(client);
    freerdp_free(client);
    return success?0:14;
}
