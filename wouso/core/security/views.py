from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.contrib.auth.models import User

from wouso.core.user.models import Player, UserReportForm
from wouso.core.security.models import Report, add_report
from wouso.interface.activity import signals

@login_required
def report(request,id):
    
    if request.user.id == int(id):
        return homepage(request, error='You cannot report yourself')
        
    get_object_or_404(User,pk=id)
    
    if request.method == "POST":
        form = UserReportForm(request.POST)
        if form.is_valid():
            user_from=request.user
            user_to = User.objects.get(pk=id)
            
            signals.addActivity.send(sender=None,
                                    user_from=user_from.get_profile().get_extension(Player),
                                    user_to=user_to.get_profile().get_extension(Player),
                                    action="report",
                                    game=None)
            add_report(user_from=user_from, user_to=user_to, text=request.POST['message'])
            request.session["report_msg"] = "The report was successfully submitted"
            return redirect('player_profile', id=id)
    else:
        form = UserReportForm()
    return render_to_response('profile/report_form.html',
                                {'id': id,'form': form},
                                context_instance=RequestContext(request))
