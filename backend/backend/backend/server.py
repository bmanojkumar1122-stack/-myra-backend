@sio.on('user_input')
async def handle_user_input(sid, data):
    # ... existing code ...
    if requires_confirmation:
        # AUTO-APPROVE - No popup
        result = await execute_tool_directly(tool_name, tool_args)
        await sio.emit('tool_result', {
            'id': tool_call_id,
            'result': result
        })